import os, subprocess, json
from mutagen.easyid3 import EasyID3
from harmonic_analyzer import estimate_key, estimate_bpm
from playlist_ingester import tag_audio_key_bpm

ROOT = "/Users/gianco/Music/Drops"

items = [
    {
        "url": "https://www.youtube.com/watch?v=qxA7kAPI5Jg",
        "artist": "Noir & Haze",
        "title": "Around (Subb-an Remix)",
        "album": "Noir Music",
        "force_phase": None # let algorithm calculate (likely 2 or 2-3A)
    },
    {
        "url": "https://www.youtube.com/watch?v=pjopVHRPmMA",
        "artist": "Tube & Berger",
        "title": "Imprint Of Pleasure (Monkey Safari Remix)",
        "album": "Suara",
        "force_phase": "5" # user specifically requested [5] Outro
    },
    {
        "url": "https://www.youtube.com/watch?v=UUeftmVOOq4",
        "artist": "Azari & III",
        "title": "Hungry For The Power (Jamie Jones Ridge Street Remix)",
        "album": "Loose Lips",
        "force_phase": None # likely 3 or 4
    }
]

for item in items:
    temp_file = os.path.join(ROOT, "temp_remix.mp3")
    artist = item["artist"]
    title = item["title"]
    album = item["album"]
    print(f"\n⬇️ Downloading: {artist} - {title}...")
    
    cmd_dl = [
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
        "--postprocessor-args", f"ffmpeg:-metadata title=\"{title}\" -metadata artist=\"{artist}\" -metadata album=\"{album}\"",
        "-o", temp_file,
        item["url"]
    ]
    subprocess.run(cmd_dl, check=True)

    print("🎼 Analyzing Key & BPM...")
    key_name, camelot_key = estimate_key(temp_file)
    bpm = estimate_bpm(temp_file)
    tag_audio_key_bpm(temp_file, key_name, camelot_key, bpm)
    round_bpm = int(round(bpm))

    if item["force_phase"]:
        phase = item["force_phase"]
    else:
        if round_bpm <= 119:
            phase = "1"
        elif round_bpm <= 124:
            if camelot_key.endswith("B"):
                phase = "2-3B"
            elif camelot_key in ["7A", "11A", "12A"]:
                phase = "2-3A"
            else:
                phase = "2"
        elif round_bpm <= 126:
            phase = "2-3A"
        elif round_bpm <= 128:
            phase = "3"
        elif round_bpm <= 132:
            phase = "4"
        else:
            phase = "4B"

    # Map phase to folder
    folder_map = {
        "1": "[1] Warm Up",
        "2": "[2] Groove Building",
        "2-3B": "[2-3B] Holding & Handover",
        "2-3A": "[2-3A] Tension Bridges",
        "3": "[3] Peak Starters",
        "4": "[4] Plateau Mentale & Climax",
        "4B": "[4B] High Velocity & Fast Peak",
        "5": "[5] Outro & Decompression"
    }

    target_folder_name = folder_map.get(phase, "[2] Groove Building")
    dest_dir = os.path.join(ROOT, target_folder_name)
    os.makedirs(dest_dir, exist_ok=True)

    clean_title = title.replace("/", "-")
    new_filename = f"[{phase}] {artist} - {clean_title} [{camelot_key} - {round_bpm}].mp3"
    dest_path = os.path.join(dest_dir, new_filename)
    if os.path.exists(dest_path):
        os.remove(dest_path)
    os.rename(temp_file, dest_path)
    print(f"✅ Archiviata in: {target_folder_name}/{new_filename}")

os.system(f"rm -f \"{ROOT}\"/*.webp")
print("\n🎉 TUTTI I REMIX COMPLETATI E ARCHIVIATI!")
