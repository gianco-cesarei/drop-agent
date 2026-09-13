#!/usr/bin/env python3
"""
Tracklist Extractor Module for Drop Agent.
Extracts and parses tracklists from YouTube descriptions, chapters, text, or LLM output.
"""

import os
import re
from typing import List, Dict, Optional


def parse_track_line(line: str) -> Optional[Dict]:
    """
    Parses a single line into track number, artist, title, remix/version.
    Examples:
      - 1. Petalpusher feat. Ledisi – "Breakin' It Down (Jay's Naked Vocal)"
      - 01 - Miguel Migs - Take Me To Paradise (Summer Lover's Dub)
      - [04:20] Janet Rushmore - On My Own (Acapella Mix)
    """
    clean_line = line.strip()
    if not clean_line:
        return None

    # Strip markdown list formatting, numbers, timestamps
    num_match = re.match(r"^(\d{1,3})[\.\-\)\s]+", clean_line)
    time_match = re.search(r"(?:\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?)", clean_line)

    track_num = None
    if num_match:
        track_num = int(num_match.group(1))
        clean_line = clean_line[num_match.end():].strip()
    elif time_match:
        clean_line = clean_line.replace(time_match.group(0), "").strip()

    # Normalize dashes and quotes: –, —, -, “ ”, " "
    clean_line = clean_line.replace("–", "-").replace("—", "-")
    clean_line = clean_line.replace('"', '').replace('"', '').replace("'", "'").strip()

    # Split by hyphen
    parts = re.split(r"\s+-\s+", clean_line, maxsplit=1)
    if len(parts) == 2:
        artist, title = parts[0].strip(), parts[1].strip()
    else:
        # Fallback if no clear artist/title split
        artist = ""
        title = clean_line

    if not title:
        return None

    return {
        "track_num": track_num,
        "artist": artist,
        "title": title,
        "full_query": f"{artist} - {title}".strip(" -")
    }


def extract_tracklist_from_text(text: str) -> List[Dict]:
    """
    Extracts a list of tracks from raw description or text.
    """
    tracks = []
    lines = text.splitlines()
    curr_idx = 1
    for line in lines:
        parsed = parse_track_line(line)
        if parsed and (parsed["artist"] or len(parsed["title"].split()) > 1):
            if not parsed["track_num"]:
                parsed["track_num"] = curr_idx
            curr_idx = max(curr_idx + 1, parsed["track_num"] + 1)
            tracks.append(parsed)
    return tracks


def extract_tracklist_blind(
    audio_path: str,
    hop_seconds: float = 60.0,
    window_duration: float = 15.0,
    concurrency_limit: int = 3,
    max_duration: Optional[float] = None
) -> List[Dict]:
    """
    Blind track recognition on raw audio file using AudioFingerprinter.
    Returns list of identified tracks with timestamps, Camelot keys, and BPM.
    """
    from fingerprinting.audio_fingerprinter import AudioFingerprinter
    fingerprinter = AudioFingerprinter(
        concurrency_limit=concurrency_limit,
        window_duration=window_duration,
        hop_seconds=hop_seconds
    )
    return fingerprinter.scan_mix(
        audio_path=audio_path,
        hop_seconds=hop_seconds,
        window_duration=window_duration,
        max_duration=max_duration
    )


def extract_or_fingerprint(
    text: Optional[str] = None,
    audio_path: Optional[str] = None,
    hop_seconds: float = 60.0
) -> List[Dict]:
    """
    Extracts tracks from description text if present; otherwise runs blind audio fingerprinting.
    """
    if text and text.strip():
        tracks = extract_tracklist_from_text(text)
        if len(tracks) >= 3:
            return tracks

    if audio_path and os.path.exists(audio_path):
        print("[Tracklist Extractor] 🧠 No text tracklist found. Initiating blind audio recognition...")
        return extract_tracklist_blind(audio_path=audio_path, hop_seconds=hop_seconds)

    return []

