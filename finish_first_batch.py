import os, subprocess
from mutagen.easyid3 import EasyID3
from harmonic_analyzer import estimate_key, estimate_bpm
from playlist_ingester import tag_audio_key_bpm

ROOT = "/Users/gianco/Music/Drops"

items = [
    {
        "artist": "Andrea Merea",
        "title": "Stargazing",
        "album": "Tangled Waves Vol.2",
        "url": "https://bosconirecords.bandcamp.com/track/andrea-merea-stargazing"
    },
    {
        "artist": "Ritmo Divino",
        "title": "Vital",
        "album": "Ritmo Divino",
        "url": "https://bosconirecords.bandcamp.com/track/vital"
    },
    {
        "artist": "Ritmo Divino",
        "title": "Ritmo Divino",
        "album": "Ritmo Divino",
        "url": "https://bosconirecords.bandcamp.com/track/ritmo-divino"
    }
]

for item in items:
    temp_file = os.path.join(ROOT, f"temp_{item['title']}.mp3")
    print(f"⬇️ Downloading: {item['artist']} - {item['title']}...")
    cmd_dl = [
        "yt-dlp",
        "--no-check-certificate",
        "-f", "ba/b",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail",
        "--add-metadata",
        "--postprocessor-args", f"ffmpeg:-metadata title=\"{item['title']}\" -metadata artist=\"{item['artist']}\" -metadata album=\"{item['album']}\"",
        "-o", temp_file,
        item["url"]
    ]
    subprocess.run(cmd_dl, check=True)

    print("🎼 Analyzing Key & BPM...")
    key_name, camelot_key = estimate_key(temp_file)
    bpm = estimate_bpm(temp_file)
    tag_audio_key_bpm(temp_file, key_name, camelot_key, bpm)
    round_bpm = int(round(bpm))

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

    safe_title = item['title'].replace("/", "-")
    new_filename = f"[{phase}] {item['artist']} - {safe_title} [{camelot_key} - {round_bpm}].mp3"
    dest_path = os.path.join(target_dir, new_filename)
    if os.path.exists(dest_path):
        os.remove(dest_path)
    os.rename(temp_file, dest_path)
    print(f"✅ Archiviata in: {os.path.basename(target_dir)}/{new_filename}")

os.system(f"rm -f \"{ROOT}\"/*.webp \"{ROOT}\"/*.jpg")
print("\n🎉 PRIMO BATCH ARCHIVIATO DEFINITIVAMENTE!")
