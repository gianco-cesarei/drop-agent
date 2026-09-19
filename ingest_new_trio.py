import os
import subprocess
import json
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from harmonic_analyzer import estimate_key, estimate_bpm
from playlist_ingester import tag_audio_key_bpm

ROOT = "/Users/gianco/Music/Drops"

tracks = [
    {
        "url": "https://pleasureclubx.bandcamp.com/track/strange-fantasy",
        "artist": "BOBBY.",
        "title": "Strange Fantasy",
        "album": "Strange Fantasy EP",
        "user_phase_hint": None,
        "default_folder": None
    },
    {
        "url": "https://iliantape.bandcamp.com/track/routine",
        "artist": "Skee Mask",
        "title": "Routine",
        "album": "ISS002",
        "user_phase_hint": "1", # User noted: 'molto da warm up questa misa'
        "default_folder": "[1] Warm Up"
    },
    {
        "url": "https://soundcloud.com/max-wiebenga/so-inagawa-logo-queen",
        "artist": "So Inagawa",
        "title": "Logo Queen",
        "album": "Logo Queen EP (Cabaret Recordings)",
        "user_phase_hint": "1", # User noted: 'anche queta molto warm'
        "default_folder": "[1] Warm Up"
    }
]

for t in tracks:
    artist = t["artist"]
    title = t["title"]
    album = t["album"]
    url = t["url"]
    
    clean_name = f"{artist} - {title}".replace("/", "-")
    temp_file = os.path.join(ROOT, f"temp_{clean_name}.mp3")
    
    print(f"\n==========================================")
    print(f"⬇️ Downloading: {artist} - {title}")
    print(f"🔗 Source: {url}")
    print(f"==========================================")
    
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
        url
    ]
    
    res = subprocess.run(cmd_dl)
    if res.returncode != 0:
        print(f"❌ Error downloading {title} from {url}")
        continue
        
    print(f"🎼 Analisi Armonica Key & BPM per {title}...")
    key_name, camelot_key = estimate_key(temp_file)
    bpm = estimate_bpm(temp_file)
    tag_audio_key_bpm(temp_file, key_name, camelot_key, bpm)
    round_bpm = int(round(bpm))
    
    print(f"📊 Rilevato: {key_name} ({camelot_key}) | {round_bpm} BPM")
    
    # Check Phase classification
    if t["user_phase_hint"] == "1":
        phase = "1"
        target_dir = os.path.join(ROOT, "[1] Warm Up")
        print(f"🎯 Applicato hint utente -> [1] Warm Up")
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
    print(f"✅ Archiviata con successo in: {os.path.basename(target_dir)}/{new_filename}")

os.system(f"rm -f \"{ROOT}\"/*.webp \"{ROOT}\"/*.jpg")
print("\n🎉 INGESTION COMPLETATA CON SUCCESSO!")
