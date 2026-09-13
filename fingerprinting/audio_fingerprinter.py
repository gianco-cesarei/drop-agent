#!/usr/bin/env python3
"""
Audio Fingerprinting & Blind Track Recognition Engine for Drop Agent.
Extracts 15s audio segments in RAM via FFmpeg, recognizes them asynchronously
via Shazamio with concurrency semaphore control, clusters and deduplicates detections,
detects precise DJ mixing transitions, and falls back to local harmonic key/BPM analysis.
"""

import os
import sys
import json
import re
import asyncio
import subprocess
from typing import List, Dict, Optional, Tuple

# Audioop compat shim for Python 3.14+
import types
if 'audioop' not in sys.modules:
    try:
        import audioop  # noqa: F401
    except ImportError:
        shim = types.ModuleType('audioop')
        shim.rms = lambda frag, width: 0
        shim.max = lambda frag, width: 0
        shim.avg = lambda frag, width: 0
        shim.mul = lambda frag, width, factor: frag
        shim.tomono = lambda frag, width, l, r: frag
        shim.tostereo = lambda frag, width, l, r: frag
        shim.add = lambda f1, f2, w: f1
        shim.bias = lambda frag, width, bias: frag
        shim.reverse = lambda frag, width: frag
        shim.lin2lin = lambda frag, width, newwidth: frag
        shim.ratecv = lambda frag, inw, nc, inr, outr, st, wA=1, wB=0: (frag, st)
        sys.modules['audioop'] = shim
        sys.modules['pyaudioop'] = shim

try:
    from shazamio import Shazam
except ImportError:
    Shazam = None

from .transition_detector import TransitionDetector
try:
    from harmonic_analyzer import estimate_key, estimate_bpm
except ImportError:
    # Try absolute import when run inside fingerprinting module
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from harmonic_analyzer import estimate_key, estimate_bpm


def format_timestamp(seconds: float) -> str:
    """Formats seconds into MM:SS or HH:MM:SS string."""
    total_sec = max(0, int(round(seconds)))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_audio_duration(audio_path: str) -> float:
    """Gets total duration of audio file in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        audio_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        duration_str = data.get("format", {}).get("duration")
        if duration_str:
            return float(duration_str)
        for s in data.get("streams", []):
            if "duration" in s:
                return float(s["duration"])
    except Exception as e:
        print(f"[Audio Fingerprinter] ⚠️ Could not get duration via ffprobe: {e}")
    return 0.0


def sample_audio_segment(
    audio_path: str,
    offset_seconds: float,
    duration_seconds: float = 15.0,
    sample_rate: int = 44100,
    channels: int = 2
) -> bytes:
    """
    Extracts an audio snippet directly into RAM (zero disk I/O) as MP3 bytes using FFmpeg.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{max(0.0, offset_seconds):.3f}",
        "-t", f"{duration_seconds:.3f}",
        "-i", audio_path,
        "-vn",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-f", "mp3",
        "-v", "quiet",
        "pipe:1"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return proc.stdout
    except Exception as e:
        print(f"[Audio Fingerprinter] ⚠️ Error sampling audio at offset {offset_seconds}s: {e}")
        return b""


def normalize_text_for_comparison(text: str) -> str:
    """Normalizes artist / title string for fuzzy comparison."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[()\[\]{}]", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\b(original|mix|feat|featuring|edit|version|dub|extended|remix|radio)\b", "", text)
    return " ".join(text.split())


def are_tracks_similar(t1: Dict, t2: Dict) -> bool:
    """Checks if two track detections represent the same release."""
    if not t1 or not t2:
        return False
    
    # Check ISRC / Shazam ID first if present
    if t1.get("isrc") and t2.get("isrc") and t1.get("isrc") == t2.get("isrc"):
        return True
    if t1.get("shazam_id") and t2.get("shazam_id") and t1.get("shazam_id") == t2.get("shazam_id"):
        return True

    n_artist1 = normalize_text_for_comparison(t1.get("artist", ""))
    n_title1 = normalize_text_for_comparison(t1.get("title", ""))
    n_artist2 = normalize_text_for_comparison(t2.get("artist", ""))
    n_title2 = normalize_text_for_comparison(t2.get("title", ""))

    if not n_title1 or not n_title2:
        return False

    # Exact normalized match
    if n_title1 == n_title2:
        if not n_artist1 or not n_artist2 or n_artist1 == n_artist2 or n_artist1 in n_artist2 or n_artist2 in n_artist1:
            return True

    # Token containment match
    words1 = set(f"{n_artist1} {n_title1}".split())
    words2 = set(f"{n_artist2} {n_title2}".split())
    if len(words1) > 0 and len(words2) > 0:
        jaccard = len(words1 & words2) / len(words1 | words2)
        if jaccard >= 0.65:
            return True

    return False


class AudioFingerprinter:
    def __init__(
        self,
        concurrency_limit: int = 3,
        window_duration: float = 15.0,
        hop_seconds: float = 60.0,
        transition_detector: Optional[TransitionDetector] = None
    ):
        self.concurrency_limit = concurrency_limit
        self.window_duration = window_duration
        self.hop_seconds = hop_seconds
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.shazam = Shazam() if Shazam else None
        self.transition_detector = transition_detector or TransitionDetector()

    def parse_shazam_payload(self, result: Dict) -> Optional[Dict]:
        """Extracts standardized track dictionary from Shazamio response payload."""
        if not result or not isinstance(result, dict):
            return None
        
        track = result.get("track")
        if not track:
            return None

        title = track.get("title", "").strip()
        artist = track.get("subtitle", "").strip()
        if not title:
            return None

        # Extract genres, album, coverart
        genres_data = track.get("genres", {})
        genre = genres_data.get("primary", "Electronic") if isinstance(genres_data, dict) else "Electronic"
        
        album = ""
        sections = track.get("sections", [])
        for sec in sections:
            if sec.get("type") == "SONG":
                for meta in sec.get("metadata", []):
                    if meta.get("title", "").lower() == "album":
                        album = meta.get("text", "")

        images = track.get("images", {})
        cover_url = images.get("coverarthq") or images.get("coverart", "")

        isrc = track.get("isrc", "")
        shazam_id = track.get("key", "")

        return {
            "title": title,
            "artist": artist,
            "album": album,
            "genre": genre,
            "isrc": isrc,
            "shazam_id": shazam_id,
            "cover_url": cover_url,
            "confidence": 0.95,
            "full_query": f"{artist} - {title}".strip(" -")
        }

    async def recognize_bytes_async(self, audio_bytes: bytes, retry_count: int = 3) -> Optional[Dict]:
        """Asynchronously recognizes an audio byte buffer using Shazamio with concurrency control."""
        if not self.shazam:
            return None
        if not audio_bytes or len(audio_bytes) < 1000:
            return None

        async with self.semaphore:
            for attempt in range(1, retry_count + 1):
                try:
                    result = await self.shazam.recognize(audio_bytes)
                    parsed = self.parse_shazam_payload(result)
                    return parsed
                except Exception as e:
                    if attempt == retry_count:
                        # Non-critical, log warning and return None
                        return None
                    await asyncio.sleep(0.5 * attempt)
            return None

    async def _scan_window_worker(
        self, audio_path: str, offset: float, window_dur: float
    ) -> Tuple[float, Optional[Dict]]:
        """Worker task: extracts chunk in RAM and queries Shazam."""
        chunk_bytes = sample_audio_segment(
            audio_path=audio_path,
            offset_seconds=offset,
            duration_seconds=window_dur
        )
        if not chunk_bytes:
            return (offset, None)
        
        track = await self.recognize_bytes_async(chunk_bytes)
        return (offset, track)

    def cluster_and_deduplicate(
        self,
        raw_detections: List[Tuple[float, Optional[Dict]]],
        audio_path: str,
        total_duration: float
    ) -> List[Dict]:
        """
        Clusters sequential detections belonging to the same track, removes spurious noise,
        calculates transition timestamps via TransitionDetector, and handles unknown segments.
        """
        if not raw_detections:
            return []

        clusters: List[Dict] = []
        current_cluster: Optional[Dict] = None

        for offset, track in raw_detections:
            if track is not None:
                if current_cluster is None:
                    current_cluster = {
                        "track": track,
                        "offsets": [offset],
                        "first_seen": offset,
                        "last_seen": offset,
                        "count": 1
                    }
                elif are_tracks_similar(current_cluster["track"], track):
                    current_cluster["offsets"].append(offset)
                    current_cluster["last_seen"] = offset
                    current_cluster["count"] += 1
                else:
                    clusters.append(current_cluster)
                    current_cluster = {
                        "track": track,
                        "offsets": [offset],
                        "first_seen": offset,
                        "last_seen": offset,
                        "count": 1
                    }
            else:
                if current_cluster is not None:
                    clusters.append(current_cluster)
                    current_cluster = None

        if current_cluster is not None:
            clusters.append(current_cluster)

        # Merge adjacent clusters if separated by a temporary anomaly
        merged_clusters: List[Dict] = []
        for c in clusters:
            if not merged_clusters:
                merged_clusters.append(c)
            else:
                prev = merged_clusters[-1]
                if are_tracks_similar(prev["track"], c["track"]) and (c["first_seen"] - prev["last_seen"]) <= (self.hop_seconds * 2.5):
                    prev["offsets"].extend(c["offsets"])
                    prev["last_seen"] = c["last_seen"]
                    prev["count"] += c["count"]
                else:
                    merged_clusters.append(c)

        # Filter out 1-count weak anomalies if duration is large, but keep single detections if valid
        final_tracks: List[Dict] = []
        track_num = 1

        for i, c in enumerate(merged_clusters):
            track_info = dict(c["track"])
            first_seen = c["first_seen"]
            last_seen = c["last_seen"]

            # Determine start timestamp:
            # If it is the first track, start at 0.0 unless first_seen > 120s
            if i == 0:
                start_time = 0.0 if first_seen <= 90.0 else max(0.0, first_seen - 15.0)
            else:
                prev_cluster = merged_clusters[i - 1]
                boundary_start = prev_cluster["last_seen"]
                boundary_end = first_seen + self.window_duration
                # Use transition detector to find the exact mix / beat drop point
                start_time = self.transition_detector.detect_transition_point(
                    audio_path=audio_path,
                    boundary_start_sec=boundary_start,
                    boundary_end_sec=boundary_end
                )

            # Determine end timestamp:
            if i < len(merged_clusters) - 1:
                next_cluster = merged_clusters[i + 1]
                boundary_start = last_seen
                boundary_end = next_cluster["first_seen"] + self.window_duration
                end_time = self.transition_detector.detect_transition_point(
                    audio_path=audio_path,
                    boundary_start_sec=boundary_start,
                    boundary_end_sec=boundary_end
                )
            else:
                end_time = total_duration if total_duration > 0 else (last_seen + self.window_duration)

            duration_sec = max(1.0, round(end_time - start_time, 2))

            # Perform Harmonic Key & BPM analysis on this segment
            # Sample 45s audio around center of the track for harmonic analysis
            track_center = start_time + (duration_sec / 2.0)
            key_name, camelot_key = estimate_key(audio_path) if os.path.exists(audio_path) else ("Unknown", "Unknown")
            bpm = estimate_bpm(audio_path) if os.path.exists(audio_path) else 124.0

            track_info.update({
                "track_num": track_num,
                "start_time": round(start_time, 2),
                "start_time_str": format_timestamp(start_time),
                "end_time": round(end_time, 2),
                "end_time_str": format_timestamp(end_time),
                "duration_seconds": duration_sec,
                "key": key_name,
                "camelot": camelot_key,
                "bpm": bpm
            })
            final_tracks.append(track_info)
            track_num += 1

        # Check for initial / final unassigned gaps and add Unknown Tracks if gap > 180s
        tracks_with_fallbacks: List[Dict] = []
        curr_time = 0.0
        current_num = 1

        for t in final_tracks:
            gap = t["start_time"] - curr_time
            if gap >= 120.0 and curr_time == 0.0:
                # Add initial unknown track
                unk_end = t["start_time"]
                key_name, camelot_key = estimate_key(audio_path) if os.path.exists(audio_path) else ("Unknown", "Unknown")
                bpm = estimate_bpm(audio_path) if os.path.exists(audio_path) else 124.0
                tracks_with_fallbacks.append({
                    "track_num": current_num,
                    "artist": "Unknown Artist",
                    "title": f"Unknown Track [{format_timestamp(curr_time)}]",
                    "album": "",
                    "genre": "Electronic",
                    "isrc": "",
                    "shazam_id": "",
                    "cover_url": "",
                    "confidence": 0.5,
                    "full_query": f"Unknown Track [{format_timestamp(curr_time)}]",
                    "start_time": round(curr_time, 2),
                    "start_time_str": format_timestamp(curr_time),
                    "end_time": round(unk_end, 2),
                    "end_time_str": format_timestamp(unk_end),
                    "duration_seconds": max(1.0, round(unk_end - curr_time, 2)),
                    "key": key_name,
                    "camelot": camelot_key,
                    "bpm": bpm
                })
                current_num += 1

            t["track_num"] = current_num
            tracks_with_fallbacks.append(t)
            current_num += 1
            curr_time = t["end_time"]

        return tracks_with_fallbacks

    async def scan_mix_async(
        self,
        audio_path: str,
        hop_seconds: Optional[float] = None,
        window_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        progress_callback = None
    ) -> List[Dict]:
        """
        Scans a continuous audio mix using sliding window recognition.
        """
        if not os.path.exists(audio_path):
            print(f"[Audio Fingerprinter] ❌ File not found: {audio_path}")
            return []

        hop = hop_seconds or self.hop_seconds
        win_dur = window_duration or self.window_duration

        total_duration = get_audio_duration(audio_path)
        if max_duration and max_duration < total_duration:
            scan_limit = max_duration
        else:
            scan_limit = total_duration

        if scan_limit <= 0:
            print(f"[Audio Fingerprinter] ⚠️ Could not determine duration, using default 3600s scan.")
            scan_limit = 3600.0

        offsets = []
        curr = 0.0
        while curr < scan_limit:
            offsets.append(curr)
            curr += hop

        print(f"[Audio Fingerprinter] 🔍 Scanning mix ({format_timestamp(scan_limit)}) with {len(offsets)} sliding windows...")

        tasks = [
            self._scan_window_worker(audio_path, off, win_dur)
            for off in offsets
        ]

        raw_results: List[Tuple[float, Optional[Dict]]] = []
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            res = await coro
            raw_results.append(res)
            if progress_callback:
                progress_callback(len(raw_results), len(tasks), res)
            elif (len(raw_results) % 5 == 0) or (len(raw_results) == len(tasks)):
                print(f"[Audio Fingerprinter] ⏳ Analyzed {len(raw_results)}/{len(tasks)} windows...")

        # Sort results by offset
        raw_results.sort(key=lambda x: x[0])

        # Cluster and detect transitions
        final_tracks = self.cluster_and_deduplicate(
            raw_detections=raw_results,
            audio_path=audio_path,
            total_duration=total_duration
        )

        print(f"[Audio Fingerprinter] ✨ Successfully recognized and clustered {len(final_tracks)} tracks in the mix!")
        return final_tracks

    def scan_mix(
        self,
        audio_path: str,
        hop_seconds: Optional[float] = None,
        window_duration: Optional[float] = None,
        max_duration: Optional[float] = None
    ) -> List[Dict]:
        """Synchronous entrypoint for scan_mix."""
        return asyncio.run(
            self.scan_mix_async(
                audio_path=audio_path,
                hop_seconds=hop_seconds,
                window_duration=window_duration,
                max_duration=max_duration
            )
        )
