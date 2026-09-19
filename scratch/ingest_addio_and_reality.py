#!/usr/bin/env python3
"""
Ingestion script for:
1. Alexander Robotnick - Addio Addio (Full Official Track + Bosco056 Artwork)
2. Lapucci - Level Of Reality (Full Bandcamp Studio Master + Bosco055 Artwork)
"""

import os
import sys
import shutil
import urllib.request
import subprocess
from pathlib import Path
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TDRC, COMM, TBPM, TKEY, APIC

sys.path.insert(0, "/Users/gianco/Documents/Claude/Projects/DropAgent")
from harmonic_analyzer import estimate_key, estimate_bpm

MUSIC_ROOT = Path("/Users/gianco/Music/Drops")
TEMP_DIR = Path("/tmp/bosconi_ingest_2")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def ingest_robotnick():
    artist = "Alexander Robotnick"
    title = "Addio Addio"
    album = "[Bosco056] My La(te)st EP"
    year = "2024"
    label = "Bosconi Records"
    genre = "Underground / Italo Disco / Electro"
    yt_url = "https://www.youtube.com/watch?v=tcMUaXS4Kdw"
    art_url = "https://f4.bcbits.com/img/a3770328316_10.jpg"
    
    print(f"\n--- Ingesting: {artist} - {title} ---")
    audio_path = TEMP_DIR / f"{artist} - {title}.mp3"
    art_path = TEMP_DIR / "bosco056.jpg"
    
    # Download audio if not already cached
    if not audio_path.exists():
        subprocess.run([
        "yt-dlp",
        "--no-check-certificate",
        "--remote-components", "ejs:github",
        "--extractor-args", "youtube:player_client=mweb,tv,web_creator",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", str(audio_path),
        yt_url
    ], check=True)
    
    # Download artwork using curl
    subprocess.run(["curl", "-sL", art_url, "-o", str(art_path)], check=True)
    
    # Harmonic analysis
    musical_key, camelot = estimate_key(str(audio_path))
    raw_bpm = estimate_bpm(str(audio_path))
    bpm = int(round(raw_bpm))
    print(f"Analysis: {camelot} ({musical_key}) @ {bpm} BPM")
    
    # Tagging
    try:
        audio = ID3(str(audio_path))
    except Exception:
        audio = ID3()
        
    audio.add(TIT2(encoding=3, text=title))
    audio.add(TPE1(encoding=3, text=artist))
    audio.add(TALB(encoding=3, text=album))
    audio.add(TCON(encoding=3, text=genre))
    audio.add(TDRC(encoding=3, text=year))
    audio.add(TBPM(encoding=3, text=str(bpm)))
    audio.add(TKEY(encoding=3, text=camelot))
    audio.add(COMM(encoding=3, lang="eng", desc="Drops Phase", text=f"Key: {camelot} | BPM: {bpm} | Label: {label}"))
    
    with open(art_path, "rb") as f:
        audio.add(APIC(
            encoding=3,
            mime="image/jpeg",
            type=3,
            desc="Cover",
            data=f.read()
        ))
    audio.save(str(audio_path), v2_version=3)
    
    # Addio is the ultimate closing track ("Addio") -> [5] Outro & Decompression
    phase_prefix = "[5]"
    phase_folder = "[5] Outro & Decompression"
    final_filename = f"{phase_prefix} {artist} - {title} [{camelot} - {bpm}].mp3"
    target_dir = MUSIC_ROOT / phase_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / final_filename
    
    shutil.move(str(audio_path), str(target_file))
    print(f"✅ Posizionato in:\n   {target_file}\n")
    return str(target_file)

def ingest_lapucci():
    artist = "Lapucci"
    title = "Level Of Reality"
    album = "[Bosco055] Level Of Control"
    year = "2024"
    label = "Bosconi Records"
    genre = "Underground / Electro / Trance"
    bc_url = "https://bosconirecords.bandcamp.com/track/level-of-reality"
    
    print(f"\n--- Ingesting: {artist} - {title} ---")
    audio_path = TEMP_DIR / f"{artist} - {title}.mp3"
    
    # Download audio with Bandcamp thumbnail embedded
    subprocess.run([
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail",
        "-o", str(audio_path),
        bc_url
    ], check=True)
    
    # Harmonic analysis
    musical_key, camelot = estimate_key(str(audio_path))
    raw_bpm = estimate_bpm(str(audio_path))
    bpm = int(round(raw_bpm))
    print(f"Analysis: {camelot} ({musical_key}) @ {bpm} BPM")
    
    # Tagging
    try:
        audio = ID3(str(audio_path))
    except Exception:
        audio = ID3()
        
    audio.add(TIT2(encoding=3, text=title))
    audio.add(TPE1(encoding=3, text=artist))
    audio.add(TALB(encoding=3, text=album))
    audio.add(TCON(encoding=3, text=genre))
    audio.add(TDRC(encoding=3, text=year))
    audio.add(TBPM(encoding=3, text=str(bpm)))
    audio.add(TKEY(encoding=3, text=camelot))
    audio.add(COMM(encoding=3, lang="eng", desc="Drops Phase", text=f"Key: {camelot} | BPM: {bpm} | Label: {label}"))
    audio.save(str(audio_path), v2_version=3)
    
    # Phase logic
    is_major = camelot.endswith("B")
    is_minor = camelot.endswith("A")
    
    if bpm <= 119:
        phase_prefix = "[1]"
        phase_folder = "[1] Warm Up"
    elif 120 <= bpm <= 124 and is_major:
        phase_prefix = "[2-3B]"
        phase_folder = "[2-3B] Holding & Handover"
    elif 120 <= bpm <= 126 and is_minor and (camelot in ["7A", "11A", "12A"]):
        phase_prefix = "[2-3A]"
        phase_folder = "[2-3A] Tension Bridges"
    elif 120 <= bpm <= 124:
        phase_prefix = "[2]"
        phase_folder = "[2] Groove Building"
    elif 125 <= bpm <= 128:
        phase_prefix = "[3]"
        phase_folder = "[3] Peak Starters"
    elif 128 <= bpm <= 132:
        phase_prefix = "[4]"
        phase_folder = "[4] Plateau Mentale & Climax"
    else:
        phase_prefix = "[4B]"
        phase_folder = "[4B] High Velocity & Fast Peak"
        
    final_filename = f"{phase_prefix} {artist} - {title} [{camelot} - {bpm}].mp3"
    target_dir = MUSIC_ROOT / phase_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / final_filename
    
    shutil.move(str(audio_path), str(target_file))
    print(f"✅ Posizionato in:\n   {target_file}\n")
    return str(target_file)

if __name__ == "__main__":
    r1 = ingest_robotnick()
    r2 = ingest_lapucci()
    print("\nIngestion completata:")
    print(f"- {r1}")
    print(f"- {r2}")
