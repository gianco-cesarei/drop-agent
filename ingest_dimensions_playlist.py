import os, sys, glob, re, subprocess, json
from mutagen.easyid3 import EasyID3
from harmonic_analyzer import estimate_key, estimate_bpm
from playlist_ingester import tag_audio_key_bpm

ROOT = "/Users/gianco/Music/Drops"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLOyNTsOGzf2Q"

# Index all existing files across Drops
existing_files_text = []
for r, d, files in os.walk(ROOT):
    for f in files:
        if f.endswith(".mp3") or f.endswith(".flac"):
            clean = re.sub(r"[^\w\s]", "", f.lower())
            existing_files_text.append(clean)

def already_exists(title: str) -> bool:
    clean_query = re.sub(r"[^\w\s]", "", title.lower())
    words = [w for w in clean_query.split() if len(w) > 3]
    if not words:
        return False
    for ex in existing_files_text:
        # If at least 3 significant words match
        matches = sum(1 for w in words if w in ex)
        if matches >= min(len(words), 3) and len(words) >= 2:
            return True
    return False

# Fetch playlist metadata
print("🔍 Recupero tracce dalla playlist Dimensions 2026...")
cmd = ["yt-dlp", PLAYLIST_URL, "--flat-playlist", "--dump-single-json"]
res = subprocess.run(cmd, capture_output=True, text=True, check=True)
data = json.loads(res.stdout)
entries = data.get("entries", [])
print(f"Totale elementi in playlist: {len(entries)}")

download_queue = []
for e in entries:
    yt_id = e.get("id")
    title = e.get("title", "")
    if already_exists(title):
        print(f"⏩ Già presente in archivio: {title}")
    else:
        download_queue.append({"id": yt_id, "title": title})

print(f"\n⚡ Tracce NUOVE da scaricare: {len(download_queue)}")

# Process each new track
for idx, item in enumerate(download_queue, 1):
    yt_id = item["id"]
    title = item["title"]
    url = f"https://www.youtube.com/watch?v={yt_id}"
    temp_file = os.path.join(ROOT, f"temp_{yt_id}.mp3")

    print(f"\n[{idx}/{len(download_queue)}] ⬇️ Downloading: {title}...")
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
        "-o", temp_file,
        url
    ]
    try:
        subprocess.run(cmd_dl, check=True)
    except Exception as exc:
        print(f"❌ Errore download {title}: {exc}")
        if os.path.exists(temp_file):
            try: os.remove(temp_file)
            except: pass
        continue

    if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 50000:
        continue

    # Harmonic Analysis
    try:
        key_name, camelot_key = estimate_key(temp_file)
        bpm = estimate_bpm(temp_file)
        tag_audio_key_bpm(temp_file, key_name, camelot_key, bpm)
        round_bpm = int(round(bpm))
    except Exception as e:
        key_name, camelot_key, round_bpm = "Unknown", "8A", 123

    # Determine Phase
    if round_bpm <= 119:
        phase = "1"
        target_dir = os.path.join(ROOT, "[1] Warm Up & Outro [5]")
    elif round_bpm <= 124:
        if camelot_key.endswith("B"):
            phase = "2-3A"
            target_dir = os.path.join(ROOT, "[2-3A] Holding & Handover")
        elif camelot_key in ["7A", "11A", "12A"]:
            phase = "2-3B"
            target_dir = os.path.join(ROOT, "[2-3B] Tension Bridges")
        else:
            phase = "2"
            target_dir = os.path.join(ROOT, "[2] Groove Building")
    elif round_bpm <= 126:
        phase = "2-3B"
        target_dir = os.path.join(ROOT, "[2-3B] Tension Bridges")
    elif round_bpm <= 128:
        phase = "3B"
        target_dir = os.path.join(ROOT, "[3B] Peak Starters")
    elif round_bpm <= 132:
        phase = "4"
        target_dir = os.path.join(ROOT, "[4] Plateau Mentale & Climax")
    else:
        phase = "4B"
        target_dir = os.path.join(ROOT, "[4B] High Velocity & Fast Peak")

    safe_title = re.sub(r'[\\/*?:"<>|]', "-", title).strip()
    new_filename = f"[{phase}] {safe_title} [{camelot_key} - {round_bpm}].mp3"
    dest_path = os.path.join(target_dir, new_filename)
    if os.path.exists(dest_path):
        new_filename = f"[{phase}] {safe_title} ({yt_id}) [{camelot_key} - {round_bpm}].mp3"
        dest_path = os.path.join(target_dir, new_filename)

    os.rename(temp_file, dest_path)
    print(f"✅ Archiviata in: {os.path.basename(target_dir)}/{new_filename}")

os.system(f"rm -f \"{ROOT}\"/*.webp")
print("\n🎉 INGESTION PLAYLIST COMPLETATA!")
