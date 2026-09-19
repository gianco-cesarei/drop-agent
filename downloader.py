#!/usr/bin/env python3
"""
Downloader and Tagging Engine for Drop Agent.
Handles high-quality audio downloading via yt-dlp and ffmpeg post-processing.
"""

import os
import json
import re
import subprocess
import tempfile
import urllib.request
from typing import Dict, Optional, List


def _clean_text(raw: str) -> str:
    """Strip boilerplate noise like (Official Video), [Premiere], vinyl positions, dates, etc."""
    cleaned = re.sub(r"^(?:(?:19|20)\d{2}[\s_.-]?\d{2,4}(?:[\s_.-]?\d{1,4})*|track[\s_-]?\d+|\d{1,3}[\s._-]+|#[0-9]{1,3}[\s._-]*)\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"[\(\[][^\(\)\[\]]*(?:official|free download|premiere|label|records|hq|hd|4k|lyric|visualizer|remastered|full album)[^\(\)\[\]]*[\)\]]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -–—:|")
    return cleaned


class DropDownloader:
    def __init__(self, output_dir: str):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def get_video_info(self, url: str) -> Dict:
        """Fetch metadata for a YouTube URL."""
        cmd = [
            "yt-dlp",
            "--no-check-certificate",
            "--remote-components", "ejs:github",
            "--extractor-args", "youtube:player_client=mweb,tv,web_creator",
            "--dump-single-json",
            "--no-playlist",
            url
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(res.stdout)
        except Exception as e:
            print(f"[Drop Agent] ⚠️ Metadata extraction error: {e}")
            return {}

    def download_full_mix(self, url: str, album_title: str, genre: str, filename: str = "00_Full_Continuous_Mix.mp3") -> Optional[str]:
        """
        Downloads the full continuous mix in high-quality MP3 (320k) with embedded cover art and metadata.
        """
        out_path = os.path.join(self.output_dir, filename)

        print(f"[Drop Agent] 🎛️  Downloading full continuous mix to: {filename}...")
        cmd = [
            "yt-dlp",
            "--no-check-certificate",
            "--remote-components", "ejs:github",
            "--extractor-args", "youtube:player_client=mweb,tv,web_creator",
            "-f", "ba/b",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--embed-thumbnail",
            "--add-metadata",
            "--postprocessor-args", f'ffmpeg:-metadata album="{album_title}" -metadata genre="{genre}" -metadata track="00"',
            "-o", out_path,
            url
        ]
        try:
            subprocess.run(cmd, check=True)
            print(f"[Drop Agent] ✅ Full mix saved: {out_path}")
            return out_path
        except Exception as e:
            print(f"[Drop Agent] ⚠️ Failed to download full continuous mix: {e}")
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
            return None

    def download_single_track(self, track_num: int, artist: str, title: str, album_title: str, genre: str, year: str = "") -> Optional[str]:
        """
        Searches for and downloads an individual track in top quality MP3 with ID3 metadata.
        Uses a resilient multi-query search cascade with format and player client fallbacks.
        """
        track_str = f"{track_num:02d}"
        safe_artist = artist.strip() or "Various Artists"
        safe_title = title.strip()
        filename = f"{track_str}. {safe_artist} - {safe_title}.mp3".replace("/", "-")
        out_path = os.path.join(self.output_dir, filename)

        if os.path.exists(out_path) and os.path.getsize(out_path) > 100000:
            print(f"[Drop Agent] ⏩ Track already exists: {filename}")
            return out_path

        clean_artist = _clean_text(safe_artist)
        clean_title = _clean_text(safe_title)

        queries = []
        seen = set()
        for candidate in [
            f"ytsearch5:{safe_artist} - {safe_title} audio",
            f"ytsearch5:{clean_artist} {clean_title}",
            f"ytsearch5:{safe_artist} - {safe_title}",
            f"ytsearch5:{clean_title}",
        ]:
            if candidate and candidate not in seen:
                seen.add(candidate)
                queries.append(candidate)

        print(f"[Drop Agent] 🔍 Searching and downloading: {track_str}. {safe_artist} – {safe_title}")

        # Post-processor args for metadata
        metadata_args = (
            f'-metadata title="{safe_title}" '
            f'-metadata artist="{safe_artist}" '
            f'-metadata album="{album_title}" '
            f'-metadata track="{track_num}" '
            f'-metadata genre="{genre}" '
        )
        if year:
            metadata_args += f'-metadata date="{year}" '

        client_args_tiers = [
            "youtube:player_client=mweb,tv,web_creator",
            "youtube:player_client=mweb,android",
            "youtube:player_client=android,ios",
        ]
        format_options = ["ba/b", "bestaudio/best", "best"]

        for q_idx, search_query in enumerate(queries):
            for tier in client_args_tiers:
                for fmt in format_options:
                    cmd = [
                        "yt-dlp",
                        "--no-check-certificate",
                        "--remote-components", "ejs:github",
                        "--extractor-args", tier,
                        "-f", fmt,
                        "-x",
                        "--audio-format", "mp3",
                        "--audio-quality", "0",
                        "--embed-thumbnail",
                        "--add-metadata",
                        "--postprocessor-args", f"ffmpeg:{metadata_args}",
                        "-o", out_path,
                        search_query
                    ]
                    try:
                        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
                            print(f"[Drop Agent] ✅ Successfully downloaded: {filename}")
                            return out_path
                    except Exception as exc:
                        if os.path.exists(out_path):
                            os.remove(out_path)
                        continue

        print(f"[Drop Agent] ❌ Could not download {filename} after all search fallbacks.")
        return None

