import os, glob, shutil

ROOT = "/Users/gianco/Music/Drops"

PHASE_FOLDERS = {
    "1": "[1] Warm Up & Outro [5]",
    "2": "[2] Groove Building",
    "2-3A": "[2-3A] Holding & Handover",
    "2-3B": "[2-3B] Tension Bridges",
    "3B": "[3B] Peak Starters",
    "4": "[4] Plateau Mentale & Climax",
    "4B": "[4B] High Velocity & Fast Peak"
}

# Create target directories
for p_dir in PHASE_FOLDERS.values():
    os.makedirs(os.path.join(ROOT, p_dir), exist_ok=True)

# Scan all folders except protected ones
PROTECTED_FOLDERS = [
    "00. Reference Sets",
    "99. HipHop & Commerciale",
    "[1] Warm Up & Outro [5]",
    "[2] Groove Building",
    "[2-3A] Holding & Handover",
    "[2-3B] Tension Bridges",
    "[3B] Peak Starters",
    "[4] Plateau Mentale & Climax",
    "[4B] High Velocity & Fast Peak"
]

all_dirs = [d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d)) and not d.startswith(".")]

moved_counts = {k: 0 for k in PHASE_FOLDERS}
total_moved = 0

for d in all_dirs:
    if d in PROTECTED_FOLDERS:
        continue
    source_dir = os.path.join(ROOT, d)
    print(f"📦 Smistamento tracce da: {d}...")
    
    mp3s = glob.glob(os.path.join(source_dir, "*.mp3"))
    for f in mp3s:
        filename = os.path.basename(f)
        if filename.startswith("["):
            phase_key = filename.split("]")[0].replace("[", "").strip()
        else:
            phase_key = "2" # fallback default
        
        target_folder_name = PHASE_FOLDERS.get(phase_key, "[2] Groove Building")
        dest_dir = os.path.join(ROOT, target_folder_name)
        dest_file = os.path.join(dest_dir, filename)
        
        # Handle possible collision
        if os.path.exists(dest_file):
            name_no_ext, ext = os.path.splitext(filename)
            dest_file = os.path.join(dest_dir, f"{name_no_ext} ({d}){ext}")
            
        shutil.move(f, dest_file)
        if phase_key in moved_counts:
            moved_counts[phase_key] += 1
        total_moved += 1
        
    # Remove old folder if empty (or only containing .DS_Store / thumbs)
    remaining = [item for item in os.listdir(source_dir) if not item.startswith(".")]
    if len(remaining) == 0:
        shutil.rmtree(source_dir)
        print(f"🗑️ Rimossa vecchia cartella svuotata: {d}")
    else:
        print(f"ℹ️ Elementi rimasti in {d}: {remaining}")

print("\n" + "="*50)
print(f"🎉 SMISTAMENTO COMPLETATO! {total_moved} tracce riorganizzate nelle cartelle di fase:")
for k, name in PHASE_FOLDERS.items():
    cnt = len(glob.glob(os.path.join(ROOT, name, "*.mp3")))
    print(f"📁 {name.ljust(35)} | {cnt} tracce")
print("="*50)
