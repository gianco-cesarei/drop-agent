import os, glob, re
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from harmonic_analyzer import estimate_key, estimate_bpm
from playlist_ingester import tag_audio_key_bpm

ROOT = "/Users/gianco/Music/Drops"
VARIE_DIR = os.path.join(ROOT, "01. Varie")

# 1. Merge Commerciale into 99. HipHop & Commerciale
hiphop_dir = os.path.join(ROOT, "99. HipHop & Commerciale")
old_hiphop = os.path.join(ROOT, "99.HipHop | Massive, Nelly")
old_comm = os.path.join(ROOT, "Commerciale")
old_rick = os.path.join(ROOT, "Never Gonna Give You Up (Electronic)")

os.makedirs(hiphop_dir, exist_ok=True)
if os.path.exists(old_hiphop):
    for f in glob.glob(os.path.join(old_hiphop, "*")):
        os.rename(f, os.path.join(hiphop_dir, os.path.basename(f)))
    try: os.rmdir(old_hiphop)
    except Exception: pass

if os.path.exists(old_comm):
    for f in glob.glob(os.path.join(old_comm, "*")):
        os.rename(f, os.path.join(hiphop_dir, os.path.basename(f)))
    try: os.rmdir(old_comm)
    except Exception: pass

if os.path.exists(old_rick):
    for f in glob.glob(os.path.join(old_rick, "*")):
        os.rename(f, os.path.join(hiphop_dir, os.path.basename(f)))
    try: os.rmdir(old_rick)
    except Exception: pass

print("✅ Cartella unificata: '99. HipHop & Commerciale' creata con successo.")

# 2. Analyze Varie
def clean_track_name(filename: str) -> str:
    base = os.path.splitext(filename)[0]
    base = re.sub(r"^\[[\w\-]+\]\s*", "", base)
    base = re.sub(r"^\d{1,3}[\.\-\s_]+\s*", "", base)
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

    try: b_float = float(bpm) if bpm else 0.0
    except Exception: b_float = 0.0

    if not key or b_float <= 0:
        k_name, cam = estimate_key(file_path)
        b_val = estimate_bpm(file_path)
        key = cam
        b_float = b_val
        tag_audio_key_bpm(file_path, k_name, cam, b_val)

    if "(" in key:
        key = key.split()[0].strip()
    round_bpm = int(round(b_float))
    return key, round_bpm

def determine_phase(bpm: int, key: str) -> str:
    if bpm <= 119:
        return "1"
    elif bpm <= 124:
        if key.endswith("B"):
            return "2-3A"
        elif key in ["7A", "11A", "12A"]:
            return "2-3B"
        else:
            return "2"
    elif bpm <= 126:
        return "2-3B"
    elif bpm <= 128:
        return "3B"
    elif bpm <= 132:
        return "4"
    else:
        return "4B"

print(f"\n🔍 Avvio analisi e catalogazione su '01. Varie'...")
mp3s = sorted(glob.glob(os.path.join(VARIE_DIR, "*.mp3")))
print(f"Totale tracce da esaminare: {len(mp3s)}")

hiphop_keywords = ["nelly", "massive attack", "eminem", "snoop", "dr. dre", "tupac", "2pac", "50 cent", "jay-z", "hip hop", "r&b", "pop", "commerciale"]

moved_to_hiphop = 0
standardized = 0

for idx, f in enumerate(mp3s, 1):
    old_name = os.path.basename(f)
    clean_name = clean_track_name(old_name)
    
    # Check if belongs to hiphop / commerciale
    is_commercial = any(kw in old_name.lower() for kw in hiphop_keywords)
    
    try:
        key, bpm = get_key_bpm(f)
        
        # Also hip-hop usually sits <110 BPM or specifically low
        if is_commercial:
            target_file = os.path.join(hiphop_dir, f"{clean_name} [{key} - {bpm}].mp3")
            os.rename(f, target_file)
            moved_to_hiphop += 1
            print(f"[{idx}/{len(mp3s)}] 📦 Spostato in HipHop/Commerciale: {clean_name}")
            continue

        phase = determine_phase(bpm, key)
        new_name = f"[{phase}] {clean_name} [{key} - {bpm}].mp3"
        new_path = os.path.join(VARIE_DIR, new_name)
        if new_path != f:
            if os.path.exists(new_path):
                new_path = os.path.join(VARIE_DIR, f"[{phase}] {clean_name} ({idx}) [{key} - {bpm}].mp3")
            os.rename(f, new_path)
            print(f"[{idx}/{len(mp3s)}] ✅ {new_name}")
        else:
            print(f"[{idx}/{len(mp3s)}] ⏩ Già ok: {new_name}")
        standardized += 1
    except Exception as e:
        print(f"[{idx}/{len(mp3s)}] ⚠️ Errore su {old_name}: {e}")

os.system(f"rm -f \"{VARIE_DIR}\"/*.webp \"{VARIE_DIR}\"/*.m3u*")
print(f"\n🎉 COMPLETATO!")
print(f"• Standardizzate in '01. Varie': {standardized}")
print(f"• Spostate in '99. HipHop & Commerciale': {moved_to_hiphop}")
