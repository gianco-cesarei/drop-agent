"""
Soulseek Client for DropSoul via slskd REST API.
Handles automated track searches, candidate ranking (bitrate/coda/lossless), and download orchestration.
"""

from __future__ import annotations

import os
import time
import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any

logger = logging.getLogger("dropsoul.soulseek")


class SoulseekDownloadStatus(str, Enum):
    QUEUED = "QUEUED"
    INITIALIZING = "INITIALIZING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NOT_FOUND = "NOT_FOUND"


@dataclass
class SoulseekSearchResult:
    username: str
    filename: str
    size_bytes: int
    bitrate_kbps: Optional[int]
    sample_rate: Optional[int]
    extension: str
    is_lossless: bool
    queue_length: int
    upload_speed_bps: int
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_320k_or_better(self) -> bool:
        if self.is_lossless:
            return True
        return (self.bitrate_kbps or 0) >= 310

    @property
    def score(self) -> float:
        """Calculates candidate quality score based on format, bitrate, and queue delay."""
        score = 0.0
        if self.is_lossless:
            score += 1000.0
        elif (self.bitrate_kbps or 0) >= 320:
            score += 800.0
        elif (self.bitrate_kbps or 0) >= 256:
            score += 500.0
        elif (self.bitrate_kbps or 0) >= 192:
            score += 300.0

        # Penalize queues
        score -= min(self.queue_length * 50.0, 400.0)

        # Bonus for fast uploaders
        if self.upload_speed_bps > 500000:
            score += 100.0

        return score


class SoulseekClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: int = 20,
        dry_run: bool = False,
    ):
        self.base_url = (base_url or os.environ.get("SLSKD_URL", "http://localhost:5030")).rstrip("/")
        self.api_key = api_key or os.environ.get("SLSKD_API_KEY", "")
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run

    def is_online(self) -> bool:
        """Checks if slskd daemon is responding."""
        if self.dry_run:
            return False
        url = f"{self.base_url}/api/v0/application"
        try:
            req = urllib.request.Request(url)
            if self.api_key:
                req.add_header("X-API-Key", self.api_key)
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def search_track(
        self,
        artist: str,
        title: str,
        wait_for_results_sec: int = 8,
        min_bitrate: int = 310,
    ) -> List[SoulseekSearchResult]:
        """
        Submits search request to slskd, waits briefly for peer responses, and parses candidates.
        """
        if self.dry_run or not self.is_online():
            logger.warning("[DropSoul] slskd is offline or in dry-run mode.")
            return []

        query = f"{artist} {title}".strip()
        search_payload = json.dumps({"searchText": query}).encode("utf-8")

        start_url = f"{self.base_url}/api/v0/searches"
        req = urllib.request.Request(
            start_url,
            data=search_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self.api_key:
            req.add_header("X-API-Key", self.api_key)

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                search_id = data.get("id")
        except Exception as e:
            logger.error(f"[DropSoul] Search submission failed: {e}")
            return []

        if not search_id:
            return []

        # Wait for search results to stream in
        time.sleep(wait_for_results_sec)

        results_url = f"{self.base_url}/api/v0/searches/{search_id}"
        req_res = urllib.request.Request(results_url)
        if self.api_key:
            req_res.add_header("X-API-Key", self.api_key)

        try:
            with urllib.request.urlopen(req_res, timeout=10) as resp:
                details = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"[DropSoul] Failed to fetch search results: {e}")
            return []

        candidates: List[SoulseekSearchResult] = []
        raw_responses = details.get("responses", [])

        for r in raw_responses:
            username = r.get("username", "")
            upload_speed = r.get("uploadSpeed", 0)
            queue_len = r.get("queueLength", 0)
            files = r.get("files", [])

            for f in files:
                filename = f.get("filename", "")
                ext = os.path.splitext(filename)[1].lower().strip(".")
                if ext not in ["mp3", "flac", "wav", "aiff", "m4a"]:
                    continue

                size = f.get("size", 0)
                bitrate = f.get("bitRate")
                sample_rate = f.get("sampleRate")
                is_lossless = ext in ["flac", "wav", "aiff"]

                if not is_lossless and (bitrate or 0) < min_bitrate:
                    continue

                candidates.append(
                    SoulseekSearchResult(
                        username=username,
                        filename=filename,
                        size_bytes=size,
                        bitrate_kbps=bitrate,
                        sample_rate=sample_rate,
                        extension=ext,
                        is_lossless=is_lossless,
                        queue_length=queue_len,
                        upload_speed_bps=upload_speed,
                        raw_response=f,
                    )
                )

        # Sort by highest score
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def get_best_match(
        self, artist: str, title: str, wait_sec: int = 8
    ) -> Optional[SoulseekSearchResult]:
        """Finds the single highest quality candidate with favorable queue position."""
        results = self.search_track(artist, title, wait_for_results_sec=wait_sec)
        return results[0] if results else None

    def enqueue_download(self, candidate: SoulseekSearchResult) -> bool:
        """Enqueues a file transfer in slskd."""
        if self.dry_run or not self.is_online():
            return False

        payload = json.dumps([{"filename": candidate.filename}]).encode("utf-8")
        url = f"{self.base_url}/api/v0/transfers/downloads/{candidate.username}"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self.api_key:
            req.add_header("X-API-Key", self.api_key)

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status in [200, 201, 202]
        except Exception as e:
            logger.error(f"[DropSoul] Download enqueue failed for {candidate.filename}: {e}")
            return False
