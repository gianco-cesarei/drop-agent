"""
Pydantic Data Models for Cloudflare R2 & Supabase Ingestion Pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DJSetModel(BaseModel):
    """Represents a full DJ Set / Continuous Mix entity."""
    id: Optional[str] = None
    title: str
    curator_or_dj: Optional[str] = "Drops Curator"
    genre: Optional[str] = "Deep House"
    source_url: str
    duration_seconds: Optional[float] = None
    average_bpm: Optional[float] = None
    initial_key: Optional[str] = None
    r2_audio_url: Optional[str] = None
    r2_artwork_url: Optional[str] = None
    track_count: Optional[int] = 0
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class TrackModel(BaseModel):
    """Represents an individual track release."""
    id: Optional[str] = None
    title: str
    artist: str
    album: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    record_label: Optional[str] = None
    catalog_number: Optional[str] = None
    release_year: Optional[str] = None
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    camelot_key: Optional[str] = None
    r2_audio_url: Optional[str] = None
    r2_artwork_url: Optional[str] = None
    buy_links: Optional[Dict[str, str]] = Field(default_factory=dict)
    source_url: Optional[str] = None


class SetTrackModel(BaseModel):
    """Association model linking tracks to a specific DJ set with cue timing."""
    set_id: str
    track_id: Optional[str] = None
    track_number: int
    artist: str
    title: str
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None
    transition_type: Optional[str] = "beatmatch"
    harmonic_delta: Optional[str] = None
    confidence_score: Optional[float] = 1.0


class IngestionReport(BaseModel):
    """Summary of Cloudflare R2 upload and Supabase sync operations."""
    set_title: str
    uploaded_files: List[str] = Field(default_factory=list)
    r2_urls: Dict[str, str] = Field(default_factory=dict)
    synced_set_id: Optional[str] = None
    synced_track_ids: List[str] = Field(default_factory=list)
    success: bool = True
    errors: List[str] = Field(default_factory=list)
