"""
Supabase PostgREST Ingestion & Synchronization Client for Drop Agent.
Performs atomic, idempotent upserts for dj_sets, tracks, and set_tracks relational tables.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
import uuid

from .models import DJSetModel, TrackModel, SetTrackModel, IngestionReport

logger = logging.getLogger("drop_agent.supabase")


class SupabaseSyncClient:
    """PostgREST client for Supabase database synchronization."""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.supabase_url = (
            supabase_url or
            os.environ.get("SUPABASE_URL", "") or
            os.environ.get("DROPS_SUPABASE_URL", "")
        ).rstrip("/")
        
        self.supabase_key = (
            supabase_key or
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or
            os.environ.get("SUPABASE_KEY", "") or
            os.environ.get("DROPS_SUPABASE_KEY", "") or
            os.environ.get("SUPABASE_ANON_KEY", "")
        ).strip()
        
        self.dry_run = dry_run

    @property
    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    def _postgrest_request(
        self,
        table: str,
        payload: List[Dict[str, Any]],
        on_conflict: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes a PostgREST bulk UPSERT with merge-duplicates resolution.
        """
        if not payload:
            return []

        if self.dry_run or not self.is_configured:
            logger.info("[DRY-RUN / LOCAL] Supabase Upsert into '%s': %d records", table, len(payload))
            return [{"id": p.get("id") or str(uuid.uuid4()), **p} for p in payload]

        endpoint = f"{self.supabase_url}/rest/v1/{table}"
        if on_conflict:
            endpoint += f"?on_conflict={on_conflict}"

        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status in (200, 201):
                    res_text = resp.read().decode("utf-8")
                    return json.loads(res_text) if res_text else []
                return []
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            logger.error("Supabase PostgREST Error %d on %s: %s", e.code, table, err_msg)
            raise RuntimeError(f"Supabase sync failed on {table} (HTTP {e.code}): {err_msg}")
        except Exception as e:
            logger.error("Supabase connection error on %s: %s", table, e)
            raise

    def sync_dj_set(self, dj_set: DJSetModel) -> Dict[str, Any]:
        """Upsert a DJ Set record into public.dj_sets table."""
        set_id = dj_set.id or str(uuid.uuid4())
        record = {
            "id": set_id,
            "title": dj_set.title,
            "curator_or_dj": dj_set.curator_or_dj,
            "genre": dj_set.genre,
            "source_url": dj_set.source_url,
            "duration_seconds": dj_set.duration_seconds,
            "average_bpm": dj_set.average_bpm,
            "initial_key": dj_set.initial_key,
            "r2_audio_url": dj_set.r2_audio_url,
            "r2_artwork_url": dj_set.r2_artwork_url,
            "track_count": dj_set.track_count,
            "metadata": dj_set.metadata or {},
        }
        res = self._postgrest_request("dj_sets", [record], on_conflict="source_url")
        return res[0] if res else record

    def sync_tracks(self, tracks: List[TrackModel]) -> List[Dict[str, Any]]:
        """Upsert track records into public.tracks table."""
        records = []
        for t in tracks:
            track_id = t.id or str(uuid.uuid4())
            records.append({
                "id": track_id,
                "title": t.title,
                "artist": t.artist,
                "album": t.album,
                "genre": t.genre,
                "style": t.style,
                "record_label": t.record_label,
                "catalog_number": t.catalog_number,
                "release_year": t.release_year,
                "bpm": t.bpm,
                "musical_key": t.musical_key,
                "camelot_key": t.camelot_key,
                "r2_audio_url": t.r2_audio_url,
                "r2_artwork_url": t.r2_artwork_url,
                "buy_links": t.buy_links or {},
                "source_url": t.source_url,
            })
        return self._postgrest_request("tracks", records, on_conflict="artist,title,record_label")

    def sync_set_tracks(self, set_tracks: List[SetTrackModel]) -> List[Dict[str, Any]]:
        """Upsert relational set-track cue points into public.set_tracks table."""
        records = []
        for st in set_tracks:
            records.append({
                "set_id": st.set_id,
                "track_id": st.track_id,
                "track_number": st.track_number,
                "artist": st.artist,
                "title": st.title,
                "start_time_seconds": st.start_time_seconds,
                "end_time_seconds": st.end_time_seconds,
                "transition_type": st.transition_type,
                "harmonic_delta": st.harmonic_delta,
                "confidence_score": st.confidence_score,
            })
        return self._postgrest_request("set_tracks", records, on_conflict="set_id,track_number")

    def sync_full_release(
        self,
        dj_set: DJSetModel,
        tracks: List[TrackModel],
        set_tracks: Optional[List[SetTrackModel]] = None
    ) -> IngestionReport:
        """Executes end-to-end relational ingestion for a DJ set release and its tracks."""
        report = IngestionReport(set_title=dj_set.title)
        try:
            # 1. Sync DJ Set
            set_record = self.sync_dj_set(dj_set)
            set_id = set_record.get("id") or dj_set.id
            report.synced_set_id = set_id

            # 2. Sync Tracks
            track_records = self.sync_tracks(tracks)
            report.synced_track_ids = [r.get("id") for r in track_records if r.get("id")]

            # 3. Sync Set-Track mappings if provided
            if set_tracks and set_id:
                for idx, st in enumerate(set_tracks):
                    st.set_id = set_id
                    if idx < len(track_records):
                        st.track_id = track_records[idx].get("id")
                self.sync_set_tracks(set_tracks)

            report.success = True
            logger.info("Successfully synced release '%s' to Supabase (%d tracks)", dj_set.title, len(tracks))
        except Exception as e:
            report.success = False
            report.errors.append(str(e))
            logger.error("Supabase release sync failed: %s", e)

        return report
