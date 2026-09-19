import os, sys, glob, re
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from harmonic_analyzer import estimate_key, estimate_bpm
from playlist_ingester import tag_audio_key_bpm

ROOT = "/Users/gianco/Music/Drops"
TARGET_FOLDERS = [
    "02. Alva Noto & Co",
    "03. Vol. 1 (Naked Music 1999) Deep House",
    "04. CABARET Label",
    "05. Houghton 2026 (Electronic & Underground)",
    "06. Dan Ghenacia",
    "07. Dimensions '26 - 2026-09-08"
]

def clean_track_name(filename: str) -> str:
    # Strip existing [1], [2], 01., 02., [8A - 123], etc.
    base = os.path.splitext(filename)[0]
    # Remove leading bracketed phase or numbers
    base = re.sub(r"^\[[\w\-]+\]\s*", "", base)
    base = re.sub(r"^\d{1,3}[\.\-\s_]+\s*", "", base)
    # Remove trailing bracketed key-bpm
    base = re.sub(r"\s*\[[0-9]{1,2}[AB]\s*-\s*\d+\]$", "", base, flags=re.IGNORECASE)
    return base.strip()

def get_key_bpm(file_path: str):
    key = None
    bpm = None
    try:
        id3 = ID3(file_path)
        if "TKEY" in id3: key = str(id3["TKEY"].text[0])
        if "TBPM" in id3: bpm = str(id3["TBPM"].text[0])
        for txxx in id3.getall("TXXX"):
            desc = txxx.desc.lower()
            if desc == "initialkey" and not key: key = str(txxx.text[0])
            elif desc == "bpm" and not bpm: bpm = str(txxx.text[0])
    except Exception:
        pass

    try:
        b_float = float(bpm) if bpm else 0.0
    except Exception:
        b_float = 0.0

    if not key or b_float <= 0:
        k_name, cam = estimate_key(file_path)
        b_val = estimate_bpm(file_path)
        key = cam
        b_float = b_val
        tag_audio_key_bpm(file_path, k_name, cam, b_val)

    # Format key
    if "(" in key:
        key = key.split()[0].strip()
    round_bpm = int(round(b_float))
    return key, round_bpm

def determine_phase(bpm: int, folder_name: str) -> str:
    if "Alva Noto" in folder_name:
        return "1"  # Ambient / Glitch / Soundscape
    if bpm <= 119:
        return "1"
    elif bpm <= 124:
        return "2"
    elif bpm <= 126:
        return "2-3B"
    elif bpm <= 128:
        return "3B"
    else:
        return "4"

for folder in TARGET_FOLDERS:
    folder_path = os.path.join(ROOT, folder)
    if not os.path.exists(folder_path):
        continue
    print(f"\n==========================================")
    print(f"📁 Processing: {folder}")
    print(f"==========================================")
    
    mp3s = sorted(glob.glob(os.path.join(folder_path, "*.mp3")))
    for idx, f in enumerate(mp3s, 1):
        old_name = os.path.basename(f)
        try:
            key, bpm = get_key_bpm(f)
            phase = determine_phase(bpm, folder)
            clean_name = clean_track_name(old_name)
            new_name = f"[{phase}] {clean_name} [{key} - {bpm}].mp3"
            
            if old_name != new_name:
                new_path = os.path.join(folder_path, new_name)
                # handle collision
                if os.path.exists(new_path) and new_path != f:
                    new_path = os.path.join(folder_path, f"[{phase}] {clean_name} ({idx}) [{key} - {bpm}].mp3")
                os.rename(f, new_path)
                print(f"[{idx}/{len(mp3s)}] ✅ {new_name}")
            else:
                print(f"[{idx}/{len(mp3s)}] ⏩ Already standard: {old_name}")
        except Exception as e:
            print(f"[{idx}/{len(mp3s)}] ⚠️ Error on {old_name}: {e}")

    # Remove temporary artifacts (.webp, .jpg leftover, .m3u)
    os.system(f"rm -f \"{folder_path}\"/*.webp \"{folder_path}\"/*.m3u*")

print("\n🎉 ALL FOLDERS STANDARDIZED TO 6-PHASE CANON!")
