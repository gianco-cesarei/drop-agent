#!/usr/bin/env python3
"""
Spotify Resolver & Parallel Ingestion Engine for Drop Agent.
Resolves Spotify Tracks, Albums, and Playlists (zero credentials needed),
extracts official metadata (Artist, Title, Album, HQ Cover Art),
downloads 320kbps MP3 audio streams in parallel,
computes Camelot Key (1A-12B) and BPM, and exports for Pioneer Rekordbox.
"""

import os
import sys
import re
import json
import ssl
import urllib.request
import urllib.parse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any

# Internal imports
sys.path.insert(0, os.path.dirname(__file__))
from harmonic_analyzer import estimate_key, estimate_bpm
from playlist_ingester import DEFAULT_AUDIO_ROOT, tag_audio_key_bpm

SSL_CTX = ssl._create_unverified_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def sanitize_filename(name: str) -> str:
    """Removes invalid filesystem characters."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    return clean.strip()


def parse_spotify_url(url: str) -> Dict[str, str]:
    """Extracts entity type ('track', 'album', 'playlist') and ID from Spotify URL."""
    clean = url.split("?")[0].strip()
    match = re.search(r"spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)", clean)
    if match:
        return {"type": match.group(1), "id": match.group(2), "clean_url": clean}
    return {"type": "unknown", "id": "", "clean_url": clean}


def resolve_spotify_entity(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetches full metadata and tracklist for any Spotify URL (Track, Album, Playlist)
    using Spotify's public embed data.
    """
    parsed = parse_spotify_url(url)
    etype = parsed.get("type")
    eid = parsed.get("id")

    if not etype or not eid:
        print(f"[Spotify Resolver] ❌ Invalid Spotify URL: {url}")
        return None

    embed_url = f"https://open.spotify.com/embed/{etype}/{eid}"
    req = urllib.request.Request(embed_url, headers=HEADERS)

    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=12) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"[Spotify Resolver] ❌ Error fetching Spotify embed: {e}")
        return None

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        print("[Spotify Resolver] ❌ Could not extract Next.js payload from Spotify.")
        return None

    try:
        data = json.loads(m.group(1))
        entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
    except Exception as e:
        print(f"[Spotify Resolver] ❌ Error parsing JSON payload: {e}")
        return None

    if not entity:
        print("[Spotify Resolver] ❌ Entity payload empty.")
        return None

    title = entity.get("title") or entity.get("name") or "Spotify Release"
    subtitle = entity.get("subtitle") or ""
    
    # Cover art URL
    cover_url = ""
    cover_art = entity.get("coverArt", {})
    sources = cover_art.get("sources", [])
    if sources:
        cover_url = sources[0].get("url", "")

    tracks_data = []

    if etype == "track":
        artists = [a.get("name") for a in entity.get("artists", []) if a.get("name")]
        artist_str = ", ".join(artists) if artists else subtitle or "Various Artists"
        tracks_data.append({
            "index": 1,
            "title": title,
            "artist": artist_str,
            "album": title,
            "cover_url": cover_url,
            "query": f"{artist_str} - {title} Official Audio"
        })
    else:
        # Album or Playlist
        raw_tracks = entity.get("trackList", [])
        for idx, t in enumerate(raw_tracks, 1):
            t_title = t.get("title", f"Track {idx}")
            t_artist = t.get("subtitle", subtitle or "Various Artists")
            tracks_data.append({
                "index": idx,
                "title": t_title,
                "artist": t_artist,
                "album": title,
                "cover_url": cover_url,
                "query": f"{t_artist} - {t_title} Audio"
            })

    return {
        "title": title,
        "type": etype,
        "cover_url": cover_url,
        "tracks": tracks_data
    }


def download_single_spotify_track(
    track_info: Dict[str, Any],
    output_dir: str,
    total: int,
    genre: str = "Electronic"
) -> Optional[Dict[str, Any]]:
    """Downloads a single Spotify track audio stream, analyzes Camelot Key & BPM, and tags ID3."""
    idx = track_info.get("index", 1)
    artist = track_info.get("artist", "Various Artists")
    title = track_info.get("title", f"Track_{idx}")
    album = track_info.get("album", "Spotify Release")
    query = track_info.get("query", f"{artist} - {title}")
    cover_url = track_info.get("cover_url", "")

    clean_artist = sanitize_filename(artist)
    clean_title = sanitize_filename(title)
    track_str = f"{idx:02d}" if total < 100 else f"{idx:03d}"
    filename = f"{track_str}. {clean_artist} - {clean_title}.mp3"
    out_path = os.path.join(output_dir, filename)

    if os.path.exists(out_path) and os.path.getsize(out_path) > 100000:
        print(f"[{idx}/{total}] ⏩ Already exists: {filename}")
        key_name, camelot_key = estimate_key(out_path)
        bpm = estimate_bpm(out_path)
        return {
            "index": idx,
            "filename": filename,
            "artist": artist,
            "title": title,
            "key": key_name,
            "camelot": camelot_key,
            "bpm": bpm,
            "file_path": out_path
        }

    print(f"[{idx}/{total}] ⬇️ Downloading: {clean_artist} – {clean_title}...")

    metadata_args = (
        f'-metadata title="{title}" '
        f'-metadata artist="{artist}" '
        f'-metadata album="{album}" '
        f'-metadata track="{idx}/{total}" '
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
        "--default-search", "ytsearch1",
        "--postprocessor-args", f"ffmpeg:{metadata_args}",
        "-o", out_path,
        f"ytsearch1:{query}"
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception as e:
        # Fallback with alternate android client
        cmd[cmd.index("youtube:player_client=mweb,tv,web_creator")] = "youtube:player_client=android,web"
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception as e2:
            print(f"[{idx}/{total}] ❌ Failed: {filename} ({e2})")
            if os.path.exists(out_path):
                try: os.remove(out_path)
                except Exception: pass
            return None

    if os.path.exists(out_path) and os.path.getsize(out_path) > 100000:
        print(f"[{idx}/{total}] 🎼 Analyzing Key & BPM: {filename}...")
        key_name, camelot_key = estimate_key(out_path)
        bpm = estimate_bpm(out_path)
        tag_audio_key_bpm(out_path, key_name, camelot_key, bpm)
        print(f"[{idx}/{total}] ✅ {camelot_key} ({key_name}) | {bpm} BPM -> {filename}")
        return {
            "index": idx,
            "filename": filename,
            "artist": artist,
            "title": title,
            "key": key_name,
            "camelot": camelot_key,
            "bpm": bpm,
            "file_path": out_path
        }
    return None


def create_spotify_tracklist_md(target_dir: str, title: str, genre: str, tracks: List[Dict[str, Any]]):
    """Generates a clean TRACKLIST.md markdown file for the DJ."""
    md_path = os.path.join(target_dir, "TRACKLIST.md")
    lines = [
        f"# 🎵 {title}",
        f"**Source:** Spotify Ingestion Engine",
        f"**Genre:** {genre}",
        f"**Total Tracks:** {len(tracks)}\n",
        "| # | Camelot | Key | BPM | Artist | Title |",
        "|---|:---:|:---:|:---:|---|---|"
    ]
    for t in tracks:
        idx = t.get("index", 1)
        cam = t.get("camelot", "N/A")
        key = t.get("key", "N/A")
        bpm = t.get("bpm", 0.0)
        art = t.get("artist", "Unknown")
        tit = t.get("title", "Unknown")
        lines.append(f"| {idx:02d} | **{cam}** | {key} | {round(bpm, 1)} | {art} | {tit} |")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def ingest_spotify_link(url: str, genre: str = "Electronic", workers: int = 4) -> Optional[Dict[str, Any]]:
    """Full parallel workflow to ingest any Spotify Link into Drops."""
    print("=" * 65)
    print(" 🟢 SPOTIFY INGESTION & REKORDBOX PREP ENGINE 🟢 ")
    print("=" * 65)

    entity = resolve_spotify_entity(url)
    if not entity or not entity.get("tracks"):
        print("[Spotify Resolver] ❌ Could not resolve tracks from Spotify URL.")
        return None

    title = entity.get("title", "Spotify Collection")
    tracks = entity.get("tracks", [])
    total_tracks = len(tracks)

    clean_folder_name = sanitize_filename(f"{title} ({genre})")
    target_dir = os.path.join(DEFAULT_AUDIO_ROOT, clean_folder_name)
    os.makedirs(target_dir, exist_ok=True)

    print(f"🎵 Title: {title} ({entity.get('type').upper()})")
    print(f"📊 Total Tracks Found: {total_tracks}")
    print(f"📂 Output Folder: {target_dir}")
    print(f"⚡ Parallel Workers: {workers}")
    print("-" * 65)

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                download_single_spotify_track,
                t,
                target_dir,
                total_tracks,
                genre
            ): t for t in tracks
        }
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    results.sort(key=lambda x: x.get("index", 0))

    if results:
        # DJ Exports
        print("\n[Spotify Engine] 🎛️ Generating Rekordbox XML & DJ files...")
        try:
            from exporters import export_all_dj_formats
            export_all_dj_formats(
                target_dir=target_dir,
                album_title=title,
                genre=genre,
                full_mix_filename=results[0]["filename"],
                tracks=results,
                performer=results[0]["artist"]
            )
        except Exception as e:
            print(f"[Spotify Ingest] DJ Export notice: {e}")

        create_spotify_tracklist_md(target_dir, title, genre, results)

        print("\n" + "=" * 65)
        print(f"🎉 SPOTIFY INGESTION COMPLETE! {len(results)}/{total_tracks} tracks ready for Pioneer CDJ.")
        print(f"📂 Location: {target_dir}")
        print("=" * 65)

    return {"target_dir": target_dir, "tracks": results}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        ingest_spotify_link(test_url)
    else:
        print("Usage: python3 spotify_resolver.py <spotify_url>")
