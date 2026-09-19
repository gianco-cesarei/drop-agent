import os, glob, shutil

ROOT = "/Users/gianco/Music/Drops"

# 1. Target folders
dir_1 = os.path.join(ROOT, "[1] Warm Up")
dir_5 = os.path.join(ROOT, "[5] Outro & Decompression")
dir_tools = os.path.join(ROOT, "[TOOLS] Rhythms & Textures")

os.makedirs(dir_5, exist_ok=True)
os.makedirs(dir_tools, exist_ok=True)

# Rename [1] Warm Up & Outro [5] to [1] Warm Up
old_dir_1 = os.path.join(ROOT, "[1] Warm Up & Outro [5]")
if os.path.exists(old_dir_1):
    os.rename(old_dir_1, dir_1)

print("📁 Create/Aggiornate cartelle:")
print(f"• {os.path.basename(dir_1)}")
print(f"• {os.path.basename(dir_5)}")
print(f"• {os.path.basename(dir_tools)}")

# 2. Identify emotional/vocal/breakbeat tracks in [1] that belong to [5]
# Outro candidate keywords or specific tracks we identified
outro_keywords = [
    "be mindfulness",
    "love me tonight",
    "the chance",
    "meditations",
    "overnight",
    "paris 1985",
    "so weit wie noch nie",
    "soft moon",
    "reverse skydiving",
    "fat s edit"
]

files_in_1 = glob.glob(os.path.join(dir_1, "*"))
moved_to_5 = 0

for f in files_in_1:
    name = os.path.basename(f).lower()
    if any(kw in name for kw in outro_keywords):
        old_name = os.path.basename(f)
        new_name = old_name.replace("[1]", "[5]", 1) if old_name.startswith("[1]") else f"[5] {old_name}"
        dest_path = os.path.join(dir_5, new_name)
        os.rename(f, dest_path)
        print(f"🌅 Spostato in [5] Outro: {new_name}")
        moved_to_5 += 1

# 3. Identify drum tools / DJ tools already across the library (e.g. keywords like 'tool', 'dub', 'drag beat')
for r, d, files in os.walk(ROOT):
    if "[TOOLS]" in r or "Reference" in r or "HipHop" in r:
        continue
    for f in files:
        f_lower = f.lower()
        if "techno disco tool" in f_lower or "drag beat" in f_lower or "workout mix" in f_lower:
            old_p = os.path.join(r, f)
            new_name = f"[TOOL] {f}" if not f.startswith("[") else f.replace(f.split("]")[0]+"]", "[TOOL]")
            dest_p = os.path.join(dir_tools, new_name)
            os.rename(old_p, dest_p)
            print(f"🥁 Spostato in [TOOLS]: {new_name}")

print(f"\n✅ Setup completato!")
print(f"• Tracce in [1] Warm Up: {len(glob.glob(os.path.join(dir_1, '*')))}")
print(f"• Tracce in [5] Outro: {len(glob.glob(os.path.join(dir_5, '*')))}")
print(f"• Tracce in [TOOLS]: {len(glob.glob(os.path.join(dir_tools, '*')))}")
