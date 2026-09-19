import os, subprocess, json
from mutagen.easyid3 import EasyID3
from harmonic_analyzer import estimate_key, estimate_bpm
from playlist_ingester import tag_audio_key_bpm

ROOT = "/Users/gianco/Music/Drops"

items = [
    {
        "title": "Virtual Empathy",
        "artist": "Alexander Robotnick",
        "album": "Simple Music",
        "force_phase": "5", # [5] Outro & Decompression
        "target_folder": "[5] Outro & Decompression"
    },
    {
        "title": "Simple Music",
        "artist": "Alexander Robotnick",
        "album": "Simple Music",
        "force_phase": None, # let key/bpm decide (Warm Up or Groove)
        "target_folder": None
    }
]

for item in items:
    title = item["title"]
    artist = item["artist"]
    album = item["album"]
    temp_file = os.path.join(ROOT, f"temp_{title}.mp3")
    
    print(f"\n⬇️ Ricerca e download: {artist} - {title}...")
    # Using specific query to bypass geoblock or generic topic mismatch
    query = f"ytsearch1:Alexander Robotnick {title} Simple Music 2022"
    cmd_dl = [
        "yt-dlp",
        "--no-check-certificate",
        "-f", "ba/b",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail",
        "--add-metadata",
        "--postprocessor-args", f"ffmpeg:-metadata title=\"{title}\" -metadata artist=\"{artist}\" -metadata album=\"{album}\"",
        "-o", temp_file,
        query
    ]
    subprocess.run(cmd_dl, check=True)

    print("🎼 Analisi Key & BPM...")
    key_name, camelot_key = estimate_key(temp_file)
    bpm = estimate_bpm(temp_file)
    tag_audio_key_bpm(temp_file, key_name, camelot_key, bpm)
    round_bpm = int(round(bpm))

    if item["force_phase"]:
        phase = item["force_phase"]
        target_dir = os.path.join(ROOT, item["target_folder"])
    else:
        if round_bpm <= 119:
            phase = "1"
            target_dir = os.path.join(ROOT, "[1] Warm Up")
        elif round_bpm <= 124:
            if camelot_key.endswith("B"):
                phase = "2-3B"
                target_dir = os.path.join(ROOT, "[2-3B] Holding & Handover")
            elif camelot_key in ["7A", "11A", "12A"]:
                phase = "2-3A"
                target_dir = os.path.join(ROOT, "[2-3A] Tension Bridges")
            else:
                phase = "2"
                target_dir = os.path.join(ROOT, "[2] Groove Building")
        elif round_bpm <= 126:
            phase = "2-3A"
            target_dir = os.path.join(ROOT, "[2-3A] Tension Bridges")
        elif round_bpm <= 128:
            phase = "3"
            target_dir = os.path.join(ROOT, "[3] Peak Starters")
        elif round_bpm <= 132:
            phase = "4"
            target_dir = os.path.join(ROOT, "[4] Plateau Mentale & Climax")
        else:
            phase = "4B"
            target_dir = os.path.join(ROOT, "[4B] High Velocity & Fast Peak")

    new_filename = f"[{phase}] {artist} - {title} [{camelot_key} - {round_bpm}].mp3"
    dest_path = os.path.join(target_dir, new_filename)
    if os.path.exists(dest_path):
        os.remove(dest_path)
    os.rename(temp_file, dest_path)
    print(f"✅ Archiviata in: {os.path.basename(target_dir)}/{new_filename}")

os.system(f"rm -f \"{ROOT}\"/*.webp \"{ROOT}\"/*.jpg")
print("\n🎉 ALEXANDER ROBOTNICK TRACKS ARCHIVIATE CON SUCCESSO!")
