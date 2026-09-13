"""
Metadata Enrichment Master Orchestrator for Drop Agent.
Coordinates Discogs & Beatport querying, artwork downloading / generation,
and ID3v2.4 audio tagging with label, catalog number, original year, key, and buy links.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .discogs_client import DiscogsClient
from .beatport_client import BeatportClient
from .artwork_manager import ArtworkManager
from .metadata_tagger import MetadataTagger

logger = logging.getLogger("drop_agent.enricher")


@dataclass
class EnrichedTrackMetadata:
    artist: str
    title: str
    album: Optional[str] = None
    track_num: Optional[int] = None
    record_label: Optional[str] = None
    catalog_number: Optional[str] = None
    original_year: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    country: Optional[str] = None
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    camelot_key: Optional[str] = None
    artwork_url: Optional[str] = None
    local_artwork_path: Optional[str] = None
    discogs_url: Optional[str] = None
    beatport_url: Optional[str] = None
    buy_links: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetadataEnricher:
    """Master orchestrator for multi-source metadata enrichment and artwork tagging."""

    def __init__(
        self,
        discogs_token: Optional[str] = None,
        cache_dir: Optional[str] = None,
        artwork_size: int = 1400,
    ):
        self.discogs = DiscogsClient(token=discogs_token, cache_dir=cache_dir)
        self.beatport = BeatportClient()
        self.artwork_manager = ArtworkManager(target_size=artwork_size)
        self.tagger = MetadataTagger()

    def enrich_track(
        self,
        artist: str,
        title: str,
        album: Optional[str] = None,
        track_num: Optional[int] = None,
        base_genre: Optional[str] = "Deep House",
        fallback_year: Optional[str] = None,
        bpm: Optional[float] = None,
        camelot_key: Optional[str] = None,
        key_name: Optional[str] = None,
    ) -> EnrichedTrackMetadata:
        """
        Queries Discogs and Beatport to assemble unified enriched metadata for a track.
        """
        logger.info("Enriching metadata for: %s - %s", artist, title)
        
        # 1. Discogs Search
        discogs_res = self.discogs.search_release(artist=artist, title=title)
        
        # 2. Beatport Search
        beatport_res = self.beatport.search_track(artist=artist, title=title)

        # Merge findings
        label = None
        catno = None
        year = fallback_year
        genre = base_genre
        style = None
        country = None
        art_url = None
        discogs_url = None
        beatport_url = None
        buy_links: Dict[str, str] = {}

        if discogs_res:
            label = discogs_res.get("label")
            catno = discogs_res.get("catalog_number")
            year = discogs_res.get("release_year") or year
            country = discogs_res.get("country")
            styles = discogs_res.get("styles", [])
            if styles:
                style = ", ".join(styles)
            genres = discogs_res.get("genres", [])
            if genres:
                genre = genres[0]
            art_url = discogs_res.get("cover_image_url")
            discogs_url = discogs_res.get("discogs_url")
            if discogs_url:
                buy_links["discogs"] = discogs_url

        if beatport_res:
            if not label:
                label = beatport_res.get("label")
            if not catno:
                catno = beatport_res.get("catalog_number")
            if not year and beatport_res.get("release_year"):
                year = beatport_res.get("release_year")
            if not art_url:
                art_url = beatport_res.get("artwork_url")
            
            beatport_url = beatport_res.get("buy_url")
            if beatport_url:
                buy_links["beatport"] = beatport_url
                
            # If BPM or Key was not provided, use Beatport's declared values
            if not bpm and beatport_res.get("bpm"):
                bpm = beatport_res.get("bpm")
            if not key_name and beatport_res.get("key"):
                key_name = beatport_res.get("key")

        return EnrichedTrackMetadata(
            artist=artist,
            title=title,
            album=album,
            track_num=track_num,
            record_label=label,
            catalog_number=catno,
            original_year=year,
            genre=genre,
            style=style,
            country=country,
            bpm=bpm,
            musical_key=key_name,
            camelot_key=camelot_key,
            artwork_url=art_url,
            discogs_url=discogs_url,
            beatport_url=beatport_url,
            buy_links=buy_links
        )

    def process_and_tag_track(
        self,
        file_path: str,
        track_info: Dict[str, Any],
        output_artwork_dir: Optional[str] = None
    ) -> EnrichedTrackMetadata:
        """
        Full pipeline: enrich metadata, download/prepare 1400x1400px cover art,
        and inject ID3v2.4 tags into the target MP3 file.
        """
        artist = track_info.get("artist", "")
        title = track_info.get("title", "")
        album = track_info.get("album_title") or track_info.get("album")
        track_num = track_info.get("track_num")
        genre = track_info.get("genre")
        bpm = track_info.get("bpm")
        camelot_key = track_info.get("camelot") or track_info.get("camelot_key")
        key_name = track_info.get("key") or track_info.get("musical_key")
        fallback_year = track_info.get("year")

        # 1. Enrich
        enriched = self.enrich_track(
            artist=artist,
            title=title,
            album=album,
            track_num=track_num,
            base_genre=genre,
            fallback_year=fallback_year,
            bpm=bpm,
            camelot_key=camelot_key,
            key_name=key_name
        )

        # 2. Cover Art Ingestion
        art_dir = output_artwork_dir or os.path.dirname(file_path)
        art_filename = f"cover_{artist}_{title}.jpg".replace("/", "-").replace(" ", "_")
        art_dest = os.path.join(art_dir, art_filename)

        local_art = None
        if enriched.artwork_url:
            local_art = self.artwork_manager.download_and_process_artwork(
                image_url=enriched.artwork_url,
                output_path=art_dest
            )

        # If no online artwork, generate high-res vinyl artwork
        if not local_art or not os.path.exists(local_art):
            local_art = self.artwork_manager.generate_fallback_artwork(
                title=title,
                artist=artist,
                label=enriched.record_label,
                genre=enriched.genre,
                output_path=art_dest
            )

        enriched.local_artwork_path = local_art

        # 3. ID3v2.4 Tagging
        if os.path.exists(file_path):
            self.tagger.tag_mp3(
                file_path=file_path,
                artist=enriched.artist,
                title=enriched.title,
                album=enriched.album,
                track_num=enriched.track_num,
                year=enriched.original_year,
                genre=enriched.genre,
                record_label=enriched.record_label,
                catalog_number=enriched.catalog_number,
                bpm=enriched.bpm,
                camelot_key=enriched.camelot_key,
                key_name=enriched.musical_key,
                cover_image_path=local_art
            )

        return enriched
