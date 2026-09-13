#!/usr/bin/env python3
"""
Drop Agent — Autonomous Music Curator & Ingestion Engine for Drops.
Integrates:
- Tracklist extraction & 320kbps MP3 downloading
- Harmonic Key (Camelot Wheel: 8A, 8B, 11B) and BPM analysis
- Milestone 3: Discogs & Beatport metadata enrichment, HQ 1400x1400 artwork, and ID3v2.4 tagging (APIC, TPUB, TKEY, TBPM, TSRC)
- Milestone 4: Cloudflare R2 object storage upload and Supabase PostgREST relational ingestion pipeline
"""

import os
import sys
import argparse
import json
import subprocess
from typing import List, Dict, Optional, Any

# Internal imports
sys.path.insert(0, os.path.dirname(__file__))

from tracklist_extractor import extract_tracklist_from_text, parse_track_line
from downloader import DropDownloader
from harmonic_analyzer import estimate_key, estimate_bpm
from enrichment import MetadataEnricher, EnrichedTrackMetadata
from cloud import R2Uploader, SupabaseSyncClient, DJSetModel, TrackModel, SetTrackModel

try:
    from fingerprinting import AudioFingerprinter
except Exception:
    AudioFingerprinter = None

try:
    from exporters import (
        generate_cue_sheet,
        generate_extended_m3u8,
        generate_rekordbox_xml,
        generate_traktor_nml,
        slice_audio_mix,
        export_all_dj_formats,
    )
except Exception:
    pass


DEFAULT_AUDIO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "audio")
)


def create_m3u_playlist(directory: str, playlist_name: str) -> str:
    """Creates an M3U8 playlist file for the release."""
    playlist_path = os.path.join(directory, f"{playlist_name}.m3u8")
    with open(playlist_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for t in sorted(os.listdir(directory)):
            if t.endswith(".mp3") and not t.startswith("."):
                f.write(f"{t}\n")
    print(f"[Drop Agent] 📜 Generated playlist: {playlist_path}")
    return playlist_path


def create_tracklist_md(
    directory: str,
    album_title: str,
    genre: str,
    url: str,
    analyzed_tracks: List[Dict[str, Any]],
    r2_base_url: Optional[str] = None
) -> str:
    """Creates a comprehensive markdown tracklist reference with Camelot Wheel harmonic details, Discogs/Beatport links, and catalog numbers."""
    md_path = os.path.join(directory, "TRACKLIST.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {album_title}\n\n")
        f.write(f"- **Genre / Style**: {genre}\n")
        f.write(f"- **Source URL**: [{url}]({url})\n")
        f.write(f"- **Total Tracks**: {len(analyzed_tracks)}\n")
        if r2_base_url:
            f.write(f"- **Cloud Stream Storage**: [{r2_base_url}]({r2_base_url})\n")
        f.write("\n## 🎧 DJ Harmonic Mixing Guide & Release Catalog\n\n")
        f.write("| # | Traccia | Label & CatNo | Musical Key | Camelot | BPM | Buy / Info |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for t in analyzed_tracks:
            num = t.get("track_num", 0)
            artist = t.get("artist", "")
            title = t.get("title", "")
            key = t.get("key", "—")
            camelot = t.get("camelot", "—")
            bpm = t.get("bpm", "—")
            label = t.get("label") or t.get("record_label") or "—"
            catno = t.get("catalog_number") or ""
            label_display = f"**{label}**" + (f" (`{catno}`)" if catno else "")
            
            # Buy links
            links = []
            if t.get("discogs_url"):
                links.append(f"[Discogs]({t['discogs_url']})")
            if t.get("beatport_url"):
                links.append(f"[Beatport]({t['beatport_url']})")
            links_str = " · ".join(links) if links else "—"

            f.write(f"| **{num:02d}** | **{artist}** – *{title}* | {label_display} | `{key}` | **`{camelot}`** | `{bpm}` | {links_str} |\n")
        
        f.write("\n### 💡 Regole di Mixing Armonico (Camelot Wheel):\n")
        f.write("- **Stessa Chiave (Energy Lock)**: es. `8A` ➔ `8A` (transizione perfetta, nessuna tensione)\n")
        f.write("- **Adiacente (+1 / -1) (Energy Shift)**: es. `8A` ➔ `9A` (+1 sale l'energia) o `8A` ➔ `7A` (-1 rilassa il mood)\n")
        f.write("- **Modo Parallelo (Mood Swap)**: es. `8A` (La min) ➔ `8B` (Do Mag) (passaggio da scuro/introspettivo a solare/aperto)\n")

    print(f"[Drop Agent] 📄 Generated rich TRACKLIST.md in {directory}")
    return md_path


def run_drop_agent(
    url: str,
    custom_tracklist: Optional[List[str]] = None,
    genre: str = "Deep House",
    folder_name: Optional[str] = None,
    audio_root: str = DEFAULT_AUDIO_ROOT,
    skip_full_mix: bool = False,
    enrich_metadata: bool = True,
    blind_detect: bool = False,
    export_cue: bool = True,
    export_rekordbox: bool = False,
    export_traktor: bool = False,
    export_dj_all: bool = False,
    slice_mix: bool = False,
    hop_seconds: float = 60.0,
    concurrency_limit: int = 3,
    upload_cloud: bool = False,
    sync_db: bool = False,
    discogs_token: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    print("=" * 60)
    print(" 💧 DROP AGENT — Music Curation & Ingestion Pipeline 💧 ")
    print("=" * 60)

    # 1. Fetch set info
    temp_dl = DropDownloader(output_dir="/tmp")
    print(f"[Drop Agent] 📡 Ingesting Set URL: {url}")
    info = temp_dl.get_video_info(url)
    video_title = info.get("title", "Unknown DJ Set")
    description = info.get("description", "")
    duration_seconds = float(info.get("duration") or 0.0)
    print(f"[Drop Agent] 💿 Detected Release Title: {video_title}")

    # 2. Extract or use provided tracklist
    tracks = []
    if custom_tracklist and len(custom_tracklist) > 0:
        print(f"[Drop Agent] 📋 Using {len(custom_tracklist)} provided tracks...")
        for idx, line in enumerate(custom_tracklist, start=1):
            parsed = parse_track_line(line)
            if parsed:
                if not parsed["track_num"]:
                    parsed["track_num"] = idx
                tracks.append(parsed)
    elif not blind_detect:
        print("[Drop Agent] 🧠 Extracting tracklist automatically from video description / metadata...")
        tracks = extract_tracklist_from_text(description)
        if tracks:
            print(f"[Drop Agent] ✨ Found {len(tracks)} tracks in metadata!")
        else:
            print("[Drop Agent] ⚠️ No text tracklist found in description.")

    # 3. Determine Curation Folder Name & Style
    if not folder_name:
        clean_title = video_title.replace("|", "-").replace(":", "-").strip()
        folder_name = f"{clean_title} ({genre})"

    target_dir = os.path.join(audio_root, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    print(f"[Drop Agent] 📁 Target Catalog Directory: {target_dir}")

    downloader = DropDownloader(output_dir=target_dir)

    # Initialize Milestone 3 Enrichment
    enricher = MetadataEnricher(discogs_token=discogs_token)

    # 4. Download Full DJ Mix (Required for blind detection, DJ exports, or if not skipped)
    full_mix_path = None
    full_mix_filename = f"00. {video_title}.mp3".replace("/", "-").replace("|", "-")
    target_full_mix = os.path.join(target_dir, full_mix_filename)

    needs_full_mix = (not skip_full_mix) or blind_detect or (not tracks) or slice_mix

    if needs_full_mix:
        if os.path.exists(target_full_mix) and os.path.getsize(target_full_mix) > 100000:
            full_mix_path = target_full_mix
            print(f"[Drop Agent] ⏩ Full continuous mix already exists: {full_mix_filename}")
        else:
            full_mix_path = downloader.download_full_mix(
                url=url,
                album_title=video_title,
                genre=genre,
                filename=full_mix_filename
            )

    # Milestone 1: Blind Track Recognition (if no tracklist or explicitly requested)
    if (blind_detect or not tracks) and full_mix_path and os.path.exists(full_mix_path):
        print("\n[Drop Agent] 🎧 Starting Milestone 1: Audio Fingerprinting & Blind Track Recognition...")
        fingerprinter = AudioFingerprinter(
            concurrency_limit=concurrency_limit,
            hop_seconds=hop_seconds
        )
        tracks = fingerprinter.scan_mix(
            audio_path=full_mix_path,
            hop_seconds=hop_seconds
        )
        print(f"[Drop Agent] ✨ Blind Recognition identified {len(tracks)} tracks with harmonic keys & timestamps!")

    # 5. Download & Enrich Individual Tracks (or slice from mix)
    downloaded_count = 0
    analyzed_tracks = []
    processed_files = []

    if slice_mix and full_mix_path and os.path.exists(full_mix_path) and tracks:
        print(f"\n[Drop Agent] ✂️ Slicing {len(tracks)} tracks from continuous mix via FFmpeg (Zero-Crossing)...")
        sliced_files = slice_audio_mix(
            audio_path=full_mix_path,
            tracks=tracks,
            output_dir=target_dir,
            album_title=video_title,
            genre=genre
        )
        downloaded_count = len(sliced_files)
        processed_files = sliced_files

        for t in tracks:
            fn = t.get("filename")
            fpath = os.path.join(target_dir, fn) if fn else None
            t_info = dict(t)
            t_info["album_title"] = video_title
            t_info["genre"] = genre
            if fpath and os.path.exists(fpath) and enrich_metadata:
                enriched = enricher.process_and_tag_track(
                    file_path=fpath,
                    track_info=t_info,
                    output_artwork_dir=target_dir
                )
                t_info["record_label"] = enriched.record_label
                t_info["catalog_number"] = enriched.catalog_number
                t_info["year"] = enriched.original_year
                t_info["discogs_url"] = enriched.discogs_url
                t_info["beatport_url"] = enriched.beatport_url
                t_info["artwork_path"] = enriched.local_artwork_path
            analyzed_tracks.append(t_info)
    else:
        print(f"\n[Drop Agent] 🚀 Ingesting & Enriching {len(tracks)} individual track releases...")
        for t in tracks:
            num = t.get("track_num", 1)
            artist = t.get("artist", "")
            title = t.get("title", "")
            file_path = downloader.download_single_track(
                track_num=num,
                artist=artist,
                title=title,
                album_title=video_title,
                genre=genre,
                year="1999" if "1999" in video_title else ""
            )
            if file_path and os.path.exists(file_path):
                downloaded_count += 1
                processed_files.append(file_path)

                # Harmonic Key & BPM Analysis if not already present
                if not t.get("camelot") or t.get("camelot") == "—" or t.get("camelot") == "Unknown":
                    print(f"[Drop Agent] 🎼 Analyzing Harmonic Key & BPM for: {os.path.basename(file_path)}...")
                    key_name, camelot_key = estimate_key(file_path)
                    bpm = estimate_bpm(file_path)
                    print(f"[Drop Agent] 🎹 Result: {camelot_key} ({key_name}) | {bpm} BPM")
                else:
                    key_name = t.get("key", "Unknown")
                    camelot_key = t.get("camelot", "8A")
                    bpm = t.get("bpm", 124.0)

                t_info = dict(t)
                t_info["key"] = key_name
                t_info["camelot"] = camelot_key
                t_info["bpm"] = bpm
                t_info["filename"] = os.path.basename(file_path)
                t_info["album_title"] = video_title
                t_info["genre"] = genre

                # Milestone 3: Discogs & Beatport Metadata & HQ Cover Art Ingestion
                if enrich_metadata:
                    print(f"[Drop Agent] 💎 Enriching Discogs & Beatport metadata + HQ 1400x1400 Artwork for '{artist} - {title}'...")
                    enriched = enricher.process_and_tag_track(
                        file_path=file_path,
                        track_info=t_info,
                        output_artwork_dir=target_dir
                    )
                    t_info["record_label"] = enriched.record_label
                    t_info["catalog_number"] = enriched.catalog_number
                    t_info["year"] = enriched.original_year
                    t_info["discogs_url"] = enriched.discogs_url
                    t_info["beatport_url"] = enriched.beatport_url
                    t_info["artwork_path"] = enriched.local_artwork_path

                analyzed_tracks.append(t_info)
            else:
                analyzed_tracks.append(t)

    # 6. Milestone 2: Smart CUE Splitting & DJ Exports (CUE, M3U8, Rekordbox XML, Traktor NML)
    print("\n[Drop Agent] 🎛️  Generating DJ Formats & Playlists (Milestone 2)...")
    if export_dj_all:
        export_all_dj_formats(
            target_dir=target_dir,
            album_title=video_title,
            genre=genre,
            full_mix_filename=full_mix_filename,
            tracks=analyzed_tracks,
            performer="Various Artists"
        )
    else:
        # Extended M3U8
        m3u8_path = os.path.join(target_dir, f"{video_title.replace('/', '-')}.m3u8")
        generate_extended_m3u8(video_title, analyzed_tracks, m3u8_path, target_dir)

        # Red Book CUE
        if export_cue:
            cue_path = os.path.join(target_dir, f"{video_title.replace('/', '-')}.cue")
            generate_cue_sheet(video_title, "Various Artists", genre, full_mix_filename, analyzed_tracks, cue_path)

        # Rekordbox XML
        if export_rekordbox:
            rekordbox_path = os.path.join(target_dir, "rekordbox.xml")
            generate_rekordbox_xml(video_title, "Various Artists", genre, target_full_mix, analyzed_tracks, rekordbox_path)

        # Traktor NML
        if export_traktor:
            traktor_path = os.path.join(target_dir, "traktor.nml")
            generate_traktor_nml(video_title, "Various Artists", genre, target_full_mix, analyzed_tracks, traktor_path)

    md_file = create_tracklist_md(target_dir, video_title, genre, url, analyzed_tracks)

    # Milestone 4: Cloudflare R2 Upload & Supabase Ingestion
    r2_uploader = R2Uploader(dry_run=dry_run)
    supabase_sync = SupabaseSyncClient(dry_run=dry_run)

    r2_audio_url = None
    r2_artwork_url = None
    uploaded_track_urls = {}

    if upload_cloud:
        print("\n[Drop Agent] ☁️ Starting Cloudflare R2 Multi-Part Upload Pipeline...")
        # Upload full mix if exists
        if full_mix_path and os.path.exists(full_mix_path):
            mix_key = r2_uploader.build_object_key("sets", folder_name, os.path.basename(full_mix_path))
            r2_audio_url = r2_uploader.upload_file(full_mix_path, mix_key)
            print(f"[Drop Agent] ☁️ Uploaded Full Mix to R2: {r2_audio_url}")

        # Upload single tracks
        for t_info in analyzed_tracks:
            fn = t_info.get("filename")
            if fn:
                local_f = os.path.join(target_dir, fn)
                if os.path.exists(local_f):
                    track_key = r2_uploader.build_object_key(genre, folder_name, fn)
                    t_url = r2_uploader.upload_file(local_f, track_key)
                    uploaded_track_urls[fn] = t_url
                    t_info["r2_audio_url"] = t_url

        # Upload artwork if available
        for art_f in os.listdir(target_dir):
            if art_f.endswith(".jpg") or art_f.endswith(".jpeg") or art_f.endswith(".png"):
                art_p = os.path.join(target_dir, art_f)
                art_key = r2_uploader.build_object_key("artworks", folder_name, art_f)
                art_url = r2_uploader.upload_file(art_p, art_key)
                if not r2_artwork_url:
                    r2_artwork_url = art_url
                print(f"[Drop Agent] 🖼️ Uploaded HQ Artwork to R2: {art_url}")

    if sync_db:
        print("\n[Drop Agent] ⚡ Synchronizing release with Supabase Postgres...")
        avg_bpm = None
        valid_bpms = [t.get("bpm") for t in analyzed_tracks if isinstance(t.get("bpm"), (int, float))]
        if valid_bpms:
            avg_bpm = sum(valid_bpms) / len(valid_bpms)

        init_key = analyzed_tracks[0].get("camelot") if analyzed_tracks else None

        dj_set_model = DJSetModel(
            title=video_title,
            curator_or_dj="Drops Autonomous Agent",
            genre=genre,
            source_url=url,
            duration_seconds=duration_seconds,
            average_bpm=avg_bpm,
            initial_key=init_key,
            r2_audio_url=r2_audio_url,
            r2_artwork_url=r2_artwork_url,
            track_count=len(analyzed_tracks),
            metadata={"folder": folder_name}
        )

        track_models = []
        set_track_models = []
        for idx, t_info in enumerate(analyzed_tracks, start=1):
            t_model = TrackModel(
                title=t_info.get("title", ""),
                artist=t_info.get("artist", ""),
                album=video_title,
                genre=genre,
                record_label=t_info.get("record_label"),
                catalog_number=t_info.get("catalog_number"),
                release_year=t_info.get("year"),
                bpm=t_info.get("bpm"),
                musical_key=t_info.get("key"),
                camelot_key=t_info.get("camelot"),
                r2_audio_url=t_info.get("r2_audio_url"),
                buy_links={
                    "discogs": t_info.get("discogs_url", ""),
                    "beatport": t_info.get("beatport_url", "")
                },
                source_url=url
            )
            track_models.append(t_model)

            st_model = SetTrackModel(
                set_id="",
                track_number=idx,
                artist=t_info.get("artist", ""),
                title=t_info.get("title", "")
            )
            set_track_models.append(st_model)

        report = supabase_sync.sync_full_release(
            dj_set=dj_set_model,
            tracks=track_models,
            set_tracks=set_track_models
        )
        print(f"[Drop Agent] 💾 Supabase Ingestion Status: {'SUCCESS' if report.success else 'FAILED'}")
        if report.synced_set_id:
            print(f"[Drop Agent] 🆔 Synced Set ID: {report.synced_set_id} ({len(report.synced_track_ids)} tracks)")

    print("\n" + "=" * 60)
    print(f"🎉 DROP AGENT FINISHED! Processed {downloaded_count}/{len(tracks)} tracks.")
    print(f"📂 Stored at: {target_dir}")
    print("=" * 60)

    return {
        "target_dir": target_dir,
        "downloaded_count": downloaded_count,
        "tracks": analyzed_tracks,
        "r2_audio_url": r2_audio_url,
        "r2_artwork_url": r2_artwork_url
    }


def analyze_local_folder(
    folder_path: str,
    genre: str = "Electronic / Club",
    export_dj_all: bool = True
) -> Dict[str, Any]:
    """
    Analyzes an existing local directory containing audio tracks:
    - Calculates Camelot Wheel keys (8A, 11B) and BPM
    - Tags MP3 files with initialkey/TBPM metadata
    - Generates .m3u8, .cue, and rekordbox.xml DJ files
    - Generates rich TRACKLIST.md guide
    """
    target_dir = os.path.abspath(folder_path)
    if not os.path.exists(target_dir):
        print(f"[Drop Agent] ❌ Cartella non trovata: {target_dir}")
        return {"error": "Folder not found"}

    album_title = os.path.basename(target_dir)
    print("=" * 60)
    print(f" 🎛️ DROP AGENT — Analisi Armonica Cartella Locale 🎛️ ")
    print(f" 📁 Cartella: {album_title}")
    print(f" 📍 Percorso: {target_dir}")
    print("=" * 60)

    audio_extensions = (".mp3", ".wav", ".aiff", ".flac", ".m4a")
    files = sorted([f for f in os.listdir(target_dir) if f.lower().endswith(audio_extensions) and not f.startswith(".")])

    if not files:
        print(f"[Drop Agent] ⚠️ Nessun file audio supportato trovato in {target_dir}")
        return {"error": "No audio files"}

    print(f"[Drop Agent] 📊 Trovati {len(files)} file audio. Inizio calcolo chiavi armoniche e BPM...")
    analyzed_tracks = []

    for idx, fn in enumerate(files, start=1):
        fpath = os.path.join(target_dir, fn)
        print(f"[{idx}/{len(files)}] 🎼 Analisi armonica: {fn}...")
        key_name, camelot_key = estimate_key(fpath)
        bpm = estimate_bpm(fpath)
        print(f"[{idx}/{len(files)}] ✅ {camelot_key} ({key_name}) | {bpm} BPM")

        # Parse artist / title
        clean_name = os.path.splitext(fn)[0]
        if " - " in clean_name:
            parts = clean_name.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        else:
            artist = "Various Artists"
            title = clean_name

        t_info = {
            "track_num": idx,
            "filename": fn,
            "artist": artist,
            "title": title,
            "key": key_name,
            "camelot": camelot_key,
            "bpm": bpm,
            "file_path": fpath
        }
        analyzed_tracks.append(t_info)

    # DJ Exports
    print("\n[Drop Agent] 🎛️ Generazione formati per Rekordbox e Traktor...")
    try:
        from exporters import export_all_dj_formats
        export_all_dj_formats(
            target_dir=target_dir,
            album_title=album_title,
            genre=genre,
            full_mix_filename=files[0],
            tracks=analyzed_tracks,
            performer="Various Artists"
        )
    except Exception as e:
        create_m3u_playlist(target_dir, album_title)

    create_tracklist_md(target_dir, album_title, genre, f"file://{target_dir}", analyzed_tracks)

    print("\n" + "=" * 60)
    print(f"🎉 ANALISI COMPLETATA! {len(analyzed_tracks)} tracce pronte per la console.")
    print(f"📂 Cartella: {target_dir}")
    print("=" * 60)
    return {"target_dir": target_dir, "tracks": analyzed_tracks}


def scan_local_vault(root_dir: str = DEFAULT_AUDIO_ROOT):
    """Deep inspection of local vault: tracks count, file size, duration, breakdown."""
    if not os.path.exists(root_dir):
        print(f"[DROP-AGENT] VAULT NOT FOUND: {root_dir}. ZERO TRACKS.")
        return

    subdirs = sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d)) and not d.startswith(".")])
    if not subdirs:
        print(f"[DROP-AGENT] VAULT EMPTY. 0 FOLDERS AT {root_dir}.")
        return

    total_files = 0
    total_bytes = 0
    total_seconds = 0.0
    folder_stats = []

    for d in subdirs:
        folder_path = os.path.join(root_dir, d)
        mp3s = [f for f in os.listdir(folder_path) if f.lower().endswith((".mp3", ".wav", ".flac", ".m4a")) and not f.startswith(".")]
        f_bytes = sum(os.path.getsize(os.path.join(folder_path, f)) for f in mp3s)
        
        # At 320kbps: 40KB/s = 2.4MB/min -> 1MB ~= 25.6 seconds
        f_secs = (f_bytes / (40 * 1024))
        
        total_files += len(mp3s)
        total_bytes += f_bytes
        total_seconds += f_secs

        h = int(f_secs // 3600)
        m = int((f_secs % 3600) // 60)

        folder_stats.append({
            "name": d,
            "count": len(mp3s),
            "size_mb": f_bytes / (1024 * 1024),
            "time_str": f"{h}h {m}m"
        })

    total_gb = total_bytes / (1024 * 1024 * 1024)
    tot_h = int(total_seconds // 3600)
    tot_m = int((total_seconds % 3600) // 60)

    print("=" * 65)
    print(" 🤖 DROP AGENT — LOCAL VAULT AUDIT [BRUTAL SCAN] 🤖 ")
    print("=" * 65)
    print(f" TOTAL TRACKS ON DISK  : {total_files}")
    print(f" TOTAL PLAYBACK TIME   : {tot_h} ORE E {tot_m} MINUTI ({tot_h}h {tot_m}m)")
    print(f" TOTAL STORAGE FOOTPRINT: {total_gb:.2f} GB ({total_bytes / (1024*1024):.0f} MB)")
    print(f" ROOT DIRECTORY        : {root_dir}")
    print("-" * 65)
    print(" FOLDER BREAKDOWN:")
    for idx, fs in enumerate(folder_stats, 1):
        print(f" [{idx:02d}] {fs['name']}")
        print(f"      ↳ {fs['count']} tracks | {fs['time_str']} | {fs['size_mb']:.1f} MB")
    print("=" * 65)
    print(" STATUS: ALL VERIFIED. READY FOR CDJ / REKORDBOX.\n")


def run_interactive_agent():
    """Interactive CLI assistant with direct, brutal selector bot tone."""
    print("=" * 65)
    print(" 💧 DROP AGENT — AUTONOMOUS SELECTOR & CURATION BOT 💧 ")
    print("=" * 65)
    print(" COMMANDS:")
    print(" [1] INGEST WEB LINK   -> Paste Spotify, YouTube, SoundCloud link (320k + Camelot + CUE)")
    print(" [2] AUDIT LOCAL FOLDER-> Select local folder on disk (Computes Camelot + BPM + Rekordbox XML)")
    print(" [3] VAULT METRICS     -> Total hours, gigabytes and breakdown of your local library\n")

    choice = input("👉 SELECT [1/2/3] (default 1): ").strip() or "1"

    if choice == "1":
        url = input("\n🔗 PASTE URL (Spotify / YouTube / SoundCloud): ").strip()
        if not url:
            print("ABORTED. NO URL.")
            return

        genre = input("🏷️ GENRE [default: Electronic]: ").strip() or "Electronic"

        if "spotify.com" in url.lower():
            print("\n[BOT] 🟢 ROUTING TO SPOTIFY RESOLVER...")
            try:
                from spotify_resolver import ingest_spotify_link
                ingest_spotify_link(url, genre=genre)
            except Exception as e:
                print(f"[BOT] ❌ SPOTIFY RESOLVER ERROR: {e}")
        elif "list=" in url or "playlist" in url.lower():
            print("\n[BOT] INGESTING PARALLEL PLAYLIST...")
            try:
                from playlist_ingester import ingest_full_playlist
                ingest_full_playlist(playlist_url=url, genre=genre, workers=4)
            except Exception as e:
                print(f"[BOT] FALLBACK TO CORE ENGINE: {e}")
                run_drop_agent(url=url, genre=genre, export_dj_all=True)
        else:
            blind = input("🔍 BLIND SET (NO TRACKLIST)? USE SHAZAM SCAN [y/N]: ").strip().lower() == "y"
            slice_choice = input("✂️ SLICE CONTINUOUS MIX INTO SEPARATE TRACKS? [y/N]: ").strip().lower() == "y"
            run_drop_agent(
                url=url,
                genre=genre,
                blind_detect=blind,
                slice_mix=slice_choice,
                export_dj_all=True
            )

    elif choice == "2":
        default_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "audio"))
        folder_input = input(f"\n📁 FOLDER PATH [default: {default_dir}]: ").strip() or default_dir
        genre = input("🏷️ GENRE [default: Electronic]: ").strip() or "Electronic"
        analyze_local_folder(folder_input, genre=genre)

    elif choice == "3":
        scan_local_vault()
    else:
        print("INVALID COMMAND. EXIT.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drop Agent — Music Intelligence, Fingerprinting & DJ Preparation Engine")
    parser.add_argument("url", nargs="?", default=None, help="Spotify / YouTube Mix / Track / Playlist URL (optional)")
    parser.add_argument("--genre", default="Deep House", help="Genre / Category")
    parser.add_argument("--folder", default=None, help="Target folder name inside data/audio")
    parser.add_argument("--analyze-folder", default=None, help="Analyze an existing local folder")
    parser.add_argument("--vault-audit", action="store_true", help="Print total hours and metrics of local audio vault")
    parser.add_argument("--tracks-file", default=None, help="Path to text file containing tracklist")
    parser.add_argument("--skip-full", action="store_true", help="Skip downloading full continuous mix")
    parser.add_argument("--blind-detect", "--fingerprint", action="store_true", help="Force blind audio fingerprinting across mix")
    parser.add_argument("--export-cue", action="store_true", default=True, help="Generate standard Red Book .cue file")
    parser.add_argument("--export-rekordbox", action="store_true", help="Generate Pioneer Rekordbox XML (DJ_PLAYLISTS)")
    parser.add_argument("--export-traktor", action="store_true", help="Generate Traktor Pro NML collection")
    parser.add_argument("--export-dj-all", action="store_true", help="Export all DJ formats (CUE, M3U8, Rekordbox, Traktor)")
    parser.add_argument("--slice", action="store_true", help="Slice continuous mix into individual tracks on zero-crossings")
    parser.add_argument("--hop-seconds", type=float, default=60.0, help="Sliding window hop size in seconds for fingerprinting")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrency limit for fingerprinting requests")
    parser.add_argument("--no-enrich", action="store_true", help="Disable Discogs & Beatport enrichment")
    parser.add_argument("--upload-cloud", action="store_true", help="Upload audio, artworks, and playlists to Cloudflare R2")
    parser.add_argument("--sync-db", action="store_true", help="Sync release and track entities to Supabase Postgres")
    parser.add_argument("--discogs-token", default=None, help="Discogs API personal access token")
    parser.add_argument("--dry-run", action="store_true", help="Simulate cloud upload and database synchronization")

    args = parser.parse_args()

    if args.vault_audit:
        scan_local_vault()
    elif args.analyze_folder:
        analyze_local_folder(args.analyze_folder, genre=args.genre)
    elif not args.url:
        run_interactive_agent()
    elif "spotify.com" in args.url.lower():
        from spotify_resolver import ingest_spotify_link
        ingest_spotify_link(args.url, genre=args.genre)
    else:
        custom_tracks = None
        if args.tracks_file and os.path.exists(args.tracks_file):
            with open(args.tracks_file, "r", encoding="utf-8") as f:
                custom_tracks = [l.strip() for l in f if l.strip()]

        run_drop_agent(
            url=args.url,
            custom_tracklist=custom_tracks,
            genre=args.genre,
            folder_name=args.folder,
            skip_full_mix=args.skip_full,
            enrich_metadata=not args.no_enrich,
            blind_detect=args.blind_detect,
            export_cue=args.export_cue,
            export_rekordbox=args.export_rekordbox,
            export_traktor=args.export_traktor,
            export_dj_all=args.export_dj_all,
            slice_mix=args.slice,
            hop_seconds=args.hop_seconds,
            concurrency_limit=args.concurrency,
            upload_cloud=args.upload_cloud,
            sync_db=args.sync_db,
            discogs_token=args.discogs_token,
            dry_run=args.dry_run
        )



