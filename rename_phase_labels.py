import os, glob, shutil

ROOT = "/Users/gianco/Music/Drops"

# 1. Rename folders using temporary names to avoid collision
old_23a = os.path.join(ROOT, "[2-3A] Holding & Handover")
old_23b = os.path.join(ROOT, "[2-3B] Tension Bridges")
old_3b  = os.path.join(ROOT, "[3B] Peak Starters")

tmp_23b = os.path.join(ROOT, "TMP_23B_Holding")
tmp_23a = os.path.join(ROOT, "TMP_23A_Tension")
tmp_3   = os.path.join(ROOT, "TMP_3_Peak")

if os.path.exists(old_23a): os.rename(old_23a, tmp_23b)
if os.path.exists(old_23b): os.rename(old_23b, tmp_23a)
if os.path.exists(old_3b):  os.rename(old_3b, tmp_3)

final_23b = os.path.join(ROOT, "[2-3B] Holding & Handover")
final_23a = os.path.join(ROOT, "[2-3A] Tension Bridges")
final_3   = os.path.join(ROOT, "[3] Peak Starters")

if os.path.exists(tmp_23b): os.rename(tmp_23b, final_23b)
if os.path.exists(tmp_23a): os.rename(tmp_23a, final_23a)
if os.path.exists(tmp_3):   os.rename(tmp_3, final_3)

print("✅ Cartelle rinominate correttamente:")
print("• [2-3B] Holding & Handover")
print("• [2-3A] Tension Bridges")
print("• [3] Peak Starters")

# 2. Update filenames inside these folders
def rename_files_prefix(folder_path, old_prefix, new_prefix):
    if not os.path.exists(folder_path): return
    files = glob.glob(os.path.join(folder_path, "*.mp3")) + glob.glob(os.path.join(folder_path, "*.flac"))
    count = 0
    for f in files:
        name = os.path.basename(f)
        if name.startswith(old_prefix):
            new_name = name.replace(old_prefix, new_prefix, 1)
            os.rename(f, os.path.join(folder_path, new_name))
            count += 1
    print(f"Aggiornati {count} file in {os.path.basename(folder_path)} ({old_prefix} -> {new_prefix})")

rename_files_prefix(final_23b, "[2-3A]", "[2-3B]")
rename_files_prefix(final_23a, "[2-3B]", "[2-3A]")
rename_files_prefix(final_3,   "[3B]",   "[3]")

# 3. Update CANONE_FASI_DJ.md
canone_file = os.path.join(ROOT, "CANONE_FASI_DJ.md")
content = """# 🎛️ CANONE DELLE FASI — DROP AGENT TAXONOMY

Guida di riferimento rapida per la selezione e l'ordinamento delle cartelle in Drops.

```
[FASE 1: Intro / Warm-up]        ───► Apertura serata (<= 119 BPM)
         │
[FASE 2: Groove Building]        ───► Costruzione ritmica / Rolling bass (120-124 BPM, Minori standard)
         │
 ┌───────┴───────────────────────────────┐
 │                                       │
 │ (Se fai OPENING)                      │ (Se sei MAIN ARTIST)
 ▼                                       ▼
[FASE 2-3B: Holding & Handover]  [FASE 2-3A: Tension Bridges]
• Tonalità MAGGIORI (B)                 • Tonalità MINORI (A: 7A, 11A)
• 123 BPM stabili, disteso              • Tensione scura pre-salto
• Consegna pulita al guest               │
                                 [FASE 3: Peak Starters]
                                 • Salto energetico (127-129 BPM)
                                 • Rottura ritmica / Drop d'impatto
                                         │
                                 [FASE 4: Plateau Mentale & Climax]
                                 • Massima velocità ipnotica (128-132 BPM)
                                 • Corsa armonica continua
                                         │
                                 [FASE 4B: High Velocity & Fast Peak]
                                 • Fast Techno / Electro / UK Bass (> 132 BPM)
                                         │
                                 [FASE 5: Outro / Decompression]
                                 • ⚠️ ATTINGERE DIRETTAMENTE DA [1]
                                 • Chiusura emotiva, vocale o downtempo
```

---

## 📌 Regole di Denominazione Tracce

Formato standard applicato ai file audio:
`[Fase] Artista - Titolo [Key - BPM].mp3`

* **`[1]`**: Intro, Warm-up e **Outro / Discesa finale [5]** (<= 119 BPM o Ambient)
* **`[2]`**: Groove Building Core (120 - 124 BPM, Minori standard 8A, 9A, 6A)
* **`[2-3B]`**: Holding & Handover (**Tonalità Maggiori B**, 120 - 124 BPM)
* **`[2-3A]`**: Tension Bridges (**Tonalità Minori A: 7A, 11A, 12A**, 120 - 126 BPM)
* **`[3]`**: Peak Starters / Rottura Energetica (127 - 128 BPM)
* **`[4]`**: Plateau Mentale, Corsa Armonica e Climax (128 - 132 BPM)
* **`[4B]`**: High Velocity & Fast Peak (> 132 BPM)
* **`[5]`**: *Attinge direttamente dal blocco [1] con profilo emotivo/vocale*
"""
with open(canone_file, "w", encoding="utf-8") as f:
    f.write(content)

print("📖 CANONE_FASI_DJ.md aggiornato con successo!")
