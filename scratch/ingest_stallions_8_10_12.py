#!/usr/bin/env python3
"""
Ingestion Script for BoscoLP05 tracks 8, 10, 12:
- Track 8: Passarani - Bungy Bungy Bungy
- Track 10: Lapucci - One 1st
- Track 12: Feel Fly - Peach
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TDRC, COMM, TBPM, TKEY

sys.path.insert(0, "/Users/gianco/Documents/Claude/Projects/DropAgent")
from harmonic_analyzer import estimate_key, estimate_bpm

TRACKS = [
    {
        "url": "https://bosconirecords.bandcamp.com/track/bungy-bungy-bungy",
        "artist": "Passarani",
        "title": "Bungy Bungy Bungy",
        "album": "[BoscoLP05] Bosconi Stallions Vol.III",
        "year": "2023",
        "label": "Bosconi Records",
        "genre": "Underground / Electro / Techno"
    },
    {
        "url": "https://bosconirecords.bandcamp.com/track/one-1st",
        "artist": "Lapucci",
        "title": "One 1st",
        "album": "[BoscoLP05] Bosconi Stallions Vol.III",
        "year": "2023",
        "label": "Bosconi Records",
        "genre": "Underground / House / Electro"
    },
    {
        "url": "https://bosconirecords.bandcamp.com/track/peach",
        "artist": "Feel Fly",
        "title": "Peach",
        "album": "[BoscoLP05] Bosconi Stallions Vol.III",
        "year": "2023",
        "label": "Bosconi Records",
        "genre": "Underground / Italo Disco / Progressive"
    }
]

MUSIC_ROOT = Path("/Users/gianco/Music/Drops")
TEMP_DIR = Path("/tmp/bosconi_ingest")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def download_and_ingest(track_info):
    temp_file = TEMP_DIR / f"{track_info['artist']} - {track_info['title']}.mp3"
    print(f"\n--- Ingesting: {track_info['artist']} - {track_info['title']} ---")
    
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail",
        "-o", str(temp_file),
        track_info["url"]
    ]
    subprocess.run(cmd, check=True)
    
    # Run harmonic analysis
    musical_key, camelot = estimate_key(str(temp_file))
    raw_bpm = estimate_bpm(str(temp_file))
    bpm = int(round(raw_bpm))
    print(f"Analysis result: {camelot} ({musical_key}) @ {bpm} BPM")
    
    # Tag file with mutagen
    try:
        audio = ID3(str(temp_file))
    except Exception:
        audio = ID3()
        
    audio.add(TIT2(encoding=3, text=track_info["title"]))
    audio.add(TPE1(encoding=3, text=track_info["artist"]))
    audio.add(TALB(encoding=3, text=track_info["album"]))
    audio.add(TCON(encoding=3, text=track_info["genre"]))
    audio.add(TDRC(encoding=3, text=track_info["year"]))
    audio.add(TBPM(encoding=3, text=str(bpm)))
    audio.add(TKEY(encoding=3, text=camelot))
    audio.add(COMM(encoding=3, lang="eng", desc="Drops Phase", text=f"Key: {camelot} | BPM: {bpm} | Label: {track_info['label']}"))
    audio.save(str(temp_file), v2_version=3)
    
    # Determine phase
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
        
    final_filename = f"{phase_prefix} {track_info['artist']} - {track_info['title']} [{camelot} - {bpm}].mp3"
    target_dir = MUSIC_ROOT / phase_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / final_filename
    
    shutil.move(str(temp_file), str(target_file))
    print(f"✅ Posizionato in:\n   {target_file}\n")
    return str(target_file)

if __name__ == "__main__":
    results = []
    for t in TRACKS:
        res = download_and_ingest(t)
        results.append(res)
    print("\nIngestion completata:")
    for r in results:
        print(f"- {r}")
