#!/usr/bin/env python3
"""
Playlist & Multi-Track Ingestion Engine for Drop Agent.
Downloads all tracks from a YouTube playlist directly in parallel (ThreadPoolExecutor),
computes Harmonic Key (Camelot Wheel 1A-12B) and BPM, writes ID3 tags with embedded thumbnails,
and generates M3U8 playlist & TRACKLIST.md.
"""

import os
import sys
import json
import re
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any

# Internal imports
sys.path.insert(0, os.path.dirname(__file__))

from harmonic_analyzer import estimate_key, estimate_bpm
from tracklist_extractor import parse_track_line

DEFAULT_AUDIO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "audio")
)


def tag_audio_key_bpm(file_path: str, key_name: str, camelot_key: str, bpm: float):
    """Tags MP3 file with Camelot Key (TKEY) and BPM (TBPM) using ffmpeg."""
    temp_out = file_path + ".temp.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i", file_path,
        "-c", "copy",
        "-metadata", f"initialkey={camelot_key}",
        "-metadata", f"KEY={camelot_key}",
        "-metadata", f"TBPM={int(round(bpm))}",
        "-metadata", f"BPM={round(bpm, 1)}",
        "-metadata", f"comment=Camelot: {camelot_key} | Key: {key_name} | {round(bpm, 1)} BPM",
        temp_out
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        os.replace(temp_out, file_path)
    except Exception as e:
        if os.path.exists(temp_out):
            try:
                os.remove(temp_out)
            except Exception:
                pass


def fetch_playlist_metadata(playlist_url: str) -> Dict[str, Any]:
    """Fetches flat JSON of all items in a playlist via yt-dlp."""
    cmd = [
        "yt-dlp",
        "--no-check-certificate",
        "--remote-components", "ejs:github",
        "--extractor-args", "youtube:player_client=mweb,tv,web_creator",
        "--flat-playlist",
        "--dump-single-json",
        playlist_url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def sanitize_filename(name: str) -> str:
    """Cleans up illegal filesystem characters."""
    return re.sub(r'[\\/*?:"<>|]', "-", name).strip()


def download_playlist_track(
    entry: Dict[str, Any],
    index: int,
    total: int,
    output_dir: str,
    album_title: str,
    genre: str = "Electronic / Underground"
) -> Optional[Dict[str, Any]]:
    """
    Downloads a single playlist entry by direct video URL, converts to MP3 320k,
    embeds artwork/metadata, and computes harmonic key & BPM.
    """
    video_id = entry.get("id")
    raw_title = entry.get("title", f"Track_{index}")
    if not video_id:
        return None

    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Parse artist / title from video title
    parsed = parse_track_line(raw_title)
    if parsed and parsed.get("artist") and parsed.get("title"):
        artist = parsed["artist"]
        title = parsed["title"]
    else:
        # Fallback split
        if " - " in raw_title:
            parts = raw_title.split(" - ", 1)
            artist, title = parts[0].strip(), parts[1].strip()
        else:
            artist = entry.get("uploader", "Various Artists") or "Various Artists"
            title = raw_title.strip()

    track_str = f"{index:03d}"
    clean_artist = sanitize_filename(artist)
    clean_title = sanitize_filename(title)
    filename = f"{track_str}. {clean_artist} - {clean_title}.mp3"
    out_path = os.path.join(output_dir, filename)

    # Check if already downloaded
    if os.path.exists(out_path) and os.path.getsize(out_path) > 100000:
        print(f"[{index}/{total}] ⏩ Already exists: {filename}")
        key_name, camelot_key = estimate_key(out_path)
        bpm = estimate_bpm(out_path)
        return {
            "index": index,
            "filename": filename,
            "artist": artist,
            "title": title,
            "key": key_name,
            "camelot": camelot_key,
            "bpm": bpm,
            "video_url": video_url,
            "file_path": out_path
        }

    print(f"[{index}/{total}] ⬇️ Downloading: {clean_artist} – {clean_title}...")

    metadata_args = (
        f'-metadata title="{title}" '
        f'-metadata artist="{artist}" '
        f'-metadata album="{album_title}" '
        f'-metadata track="{index}/{total}" '
        f'-metadata genre="{genre}" '
    )

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
        "--postprocessor-args", f"ffmpeg:{metadata_args}",
        "-o", out_path,
        video_url
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception as e:
        # Fallback to android client if mweb fails
        cmd[cmd.index("youtube:player_client=mweb,tv,web_creator")] = "youtube:player_client=android,web"
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception as e2:
            print(f"[{index}/{total}] ❌ Failed: {filename} ({e2})")
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except Exception:
                    pass
            return None

    if os.path.exists(out_path) and os.path.getsize(out_path) > 100000:
        print(f"[{index}/{total}] 🎼 Analyzing Key & BPM: {filename}...")
        key_name, camelot_key = estimate_key(out_path)
        bpm = estimate_bpm(out_path)
        tag_audio_key_bpm(out_path, key_name, camelot_key, bpm)
        print(f"[{index}/{total}] ✅ {camelot_key} ({key_name}) | {bpm} BPM -> {filename}")
        return {
            "index": index,
            "filename": filename,
            "artist": artist,
            "title": title,
            "key": key_name,
            "camelot": camelot_key,
            "bpm": bpm,
            "video_url": video_url,
            "file_path": out_path
        }

    return None


def generate_playlist_files(output_dir: str, playlist_title: str, genre: str, url: str, items: List[Dict[str, Any]]):
    """Creates M3U8 playlist & rich TRACKLIST.md in the folder."""
    # 1. M3U8
    m3u_path = os.path.join(output_dir, f"{sanitize_filename(playlist_title)}.m3u8")
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in sorted(items, key=lambda x: x["index"]):
            f.write(f"#EXTINF:-1,{item['artist']} - {item['title']}\n")
            f.write(f"{item['filename']}\n")

    # 2. TRACKLIST.md
    md_path = os.path.join(output_dir, "TRACKLIST.md")
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write(f"# {playlist_title}\n\n")
        mf.write(f"- **Genre / Style**: {genre}\n")
        mf.write(f"- **Source Playlist URL**: [{url}]({url})\n")
        mf.write(f"- **Total Tracks Ingested**: {len(items)}\n\n")
        mf.write("## 🎧 DJ Harmonic Mixing Guide (Camelot Wheel & BPM)\n\n")
        mf.write("| # | Traccia | Musical Key | Camelot | BPM | Video Link |\n")
        mf.write("|:---:|---|---|:---:|:---:|:---:|\n")
        for item in sorted(items, key=lambda x: x["index"]):
            idx = item["index"]
            art = item["artist"]
            tit = item["title"]
            k = item.get("key", "—")
            c = item.get("camelot", "—")
            b = item.get("bpm", "—")
            vurl = item.get("video_url", "#")
            mf.write(f"| **{idx:03d}** | **{art}** – *{tit}* | `{k}` | **`{c}`** | `{b}` | [YouTube]({vurl}) |\n")

        mf.write("\n### 💡 Regole di Mixing Armonico (Camelot Wheel):\n")
        mf.write("- **Stessa Chiave (Energy Lock)**: es. `8A` ➔ `8A` (massima fusione melodica)\n")
        mf.write("- **Adiacente (+1 / -1) (Energy Shift)**: es. `8A` ➔ `9A` (aumenta energia) o `8A` ➔ `7A` (rilassa atmosfera)\n")
        mf.write("- **Modo Parallelo (Mood Swap)**: es. `8A` (La min) ➔ `8B` (Do Mag) (transizione aperta/vocale)\n")

    print(f"[Drop Agent] 📜 Generated Playlist: {m3u_path}")
    print(f"[Drop Agent] 📄 Generated Markdown: {md_path}")


def ingest_full_playlist(
    playlist_url: str,
    genre: str = "Electronic / Houghton Festival",
    folder_name: Optional[str] = None,
    workers: int = 4,
    audio_root: str = DEFAULT_AUDIO_ROOT
):
    print("=" * 65)
    print(" 💧 DROP AGENT — High-Speed Parallel Playlist Ingestion 💧 ")
    print("=" * 65)

    print(f"[Drop Agent] 📡 Fetching playlist metadata: {playlist_url}")
    pl_data = fetch_playlist_metadata(playlist_url)
    pl_title = pl_data.get("title", "YouTube Playlist")
    entries = pl_data.get("entries", [])

    print(f"[Drop Agent] 💿 Playlist Title: {pl_title}")
    print(f"[Drop Agent] 📊 Found {len(entries)} tracks in playlist.")

    if not folder_name:
        folder_name = sanitize_filename(f"{pl_title} ({genre})")

    target_dir = os.path.join(audio_root, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    print(f"[Drop Agent] 📁 Target Catalog Directory: {target_dir}")
    print(f"[Drop Agent] ⚡ Parallel Workers: {workers}")

    completed_items = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                download_playlist_track,
                entry=entry,
                index=idx,
                total=len(entries),
                output_dir=target_dir,
                album_title=pl_title,
                genre=genre
            ): idx
            for idx, entry in enumerate(entries, start=1)
        }

        for future in as_completed(futures):
            res = future.result()
            if res:
                completed_items.append(res)

    print("\n" + "=" * 65)
    print(f"🎉 PLAYLIST INGESTION COMPLETE! {len(completed_items)}/{len(entries)} tracks downloaded.")
    print("=" * 65)

    # Generate M3U8 & Markdown
    generate_playlist_files(target_dir, pl_title, genre, playlist_url, completed_items)
    return target_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drop Agent — Parallel Playlist Ingestion")
    parser.add_argument("url", help="YouTube Playlist URL")
    parser.add_argument("--genre", default="Electronic / Houghton Festival", help="Genre / Category")
    parser.add_argument("--folder", default=None, help="Target folder inside data/audio")
    parser.add_argument("--workers", type=int, default=4, help="Parallel download workers (default 4)")

    args = parser.parse_args()
    ingest_full_playlist(
        playlist_url=args.url,
        genre=args.genre,
        folder_name=args.folder,
        workers=args.workers
    )
