"""
DropSoul Queue Manager.
Manages asynchronous hunting queue for tracks in status:
- PENDING_HUNT (Waiting for peer online / HQ download)
- DOWNSIZED_PLACEHOLDER (Temporary WebRip active, awaiting upgrade)
- VERIFIED_HQ (Upgraded and certified >20kHz)
- SKIPPED (Excluded by user)
Supports dual-persistence: Local JSON cache + Supabase PostgREST sync.
"""

from __future__ import annotations

import os
import json
import time
import uuid
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Dict, Optional, Any

logger = logging.getLogger("dropsoul.queue")


class QueueStatus(str, Enum):
    PENDING_HUNT = "PENDING_HUNT"                      # In queue waiting for HQ release on Soulseek
    DOWNSIZED_PLACEHOLDER = "DOWNSIZED_PLACEHOLDER"    # WebRip in use, background hunt active
    VERIFIED_HQ = "VERIFIED_HQ"                        # Genuine FLAC / 320k downloaded and verified
    SKIPPED = "SKIPPED"                                # Excluded


@dataclass
class QueueTrackItem:
    id: str
    artist: str
    title: str
    album_title: str
    status: QueueStatus
    downsized_file_path: Optional[str] = None
    hq_file_path: Optional[str] = None
    r2_url: Optional[str] = None
    cutoff_hz: Optional[float] = None
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QueueTrackItem:
        status_val = data.get("status", QueueStatus.PENDING_HUNT.value)
        try:
            status = QueueStatus(status_val)
        except ValueError:
            status = QueueStatus.PENDING_HUNT
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            artist=data.get("artist", ""),
            title=data.get("title", ""),
            album_title=data.get("album_title", ""),
            status=status,
            downsized_file_path=data.get("downsized_file_path"),
            hq_file_path=data.get("hq_file_path"),
            r2_url=data.get("r2_url"),
            cutoff_hz=data.get("cutoff_hz"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


class DropSoulQueueManager:
    def __init__(
        self,
        local_db_path: Optional[str] = None,
        supabase_client: Optional[Any] = None,
    ):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
        os.makedirs(base_dir, exist_ok=True)
        self.local_db_path = local_db_path or os.path.join(base_dir, "dropsoul_queue.json")
        self.supabase_client = supabase_client
        self._items: Dict[str, QueueTrackItem] = {}
        self._load_local()

    def _load_local(self) -> None:
        if os.path.exists(self.local_db_path):
            try:
                with open(self.local_db_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    for item_data in raw:
                        item = QueueTrackItem.from_dict(item_data)
                        self._items[item.id] = item
            except Exception as e:
                logger.error(f"[DropSoul Queue] Failed to load local queue: {e}")

    def _save_local(self) -> None:
        try:
            data = [item.to_dict() for item in self._items.values()]
            with open(self.local_db_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[DropSoul Queue] Failed to save local queue: {e}")

    def add_track(
        self,
        artist: str,
        title: str,
        album_title: str,
        status: QueueStatus,
        downsized_file_path: Optional[str] = None,
    ) -> QueueTrackItem:
        """Adds or updates a track in the DropSoul hunting queue."""
        # Avoid duplicate pending items
        for existing in self._items.values():
            if (
                existing.artist.strip().lower() == artist.strip().lower()
                and existing.title.strip().lower() == title.strip().lower()
                and existing.album_title.strip().lower() == album_title.strip().lower()
            ):
                existing.status = status
                if downsized_file_path:
                    existing.downsized_file_path = downsized_file_path
                existing.updated_at = time.time()
                self._save_local()
                return existing

        item_id = str(uuid.uuid4())
        item = QueueTrackItem(
            id=item_id,
            artist=artist.strip(),
            title=title.strip(),
            album_title=album_title.strip(),
            status=status,
            downsized_file_path=downsized_file_path,
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._items[item_id] = item
        self._save_local()
        logger.info(f"[DropSoul Queue] 🎯 Queued for hunt: '{artist} - {title}' [{status.value}]")
        return item

    def get_pending_hunts(self) -> List[QueueTrackItem]:
        """Returns all tracks still waiting for HQ upgrade."""
        return [
            item
            for item in self._items.values()
            if item.status in [QueueStatus.PENDING_HUNT, QueueStatus.DOWNSIZED_PLACEHOLDER]
        ]

    def mark_completed_hq(
        self,
        item_id: str,
        hq_file_path: str,
        cutoff_hz: float,
        r2_url: Optional[str] = None,
    ) -> Optional[QueueTrackItem]:
        """Updates track to VERIFIED_HQ once acquired and validated."""
        item = self._items.get(item_id)
        if not item:
            return None
        item.status = QueueStatus.VERIFIED_HQ
        item.hq_file_path = hq_file_path
        item.cutoff_hz = cutoff_hz
        if r2_url:
            item.r2_url = r2_url
        item.updated_at = time.time()
        self._save_local()
        logger.info(f"[DropSoul Queue] ✅ Track upgraded to VERIFIED_HQ: '{item.artist} - {item.title}'")
        return item
