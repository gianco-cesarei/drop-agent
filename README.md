# 💧 Drop Agent Workspace

Ambiente dedicato e autonomo per **Drop Agent** — Music Curator, DJ Ingestion Engine & Audio Archivist ad alta fedeltà.

---

## 🎧 Come Usarlo in questo Workspace

Incolla semplicemente il link di un DJ Set, album o mix (YouTube / SoundCloud) o una lista di tracce all'agente Antigravity, ad esempio:

> *"Scarica e cura questo set: https://www.youtube.com/watch?v=... genere Deep House"*

Oppure da terminale:
```bash
# Esempio download completo con estrazione automatica tracklist e analisi Camelot/BPM
python3 drop_agent.py "https://www.youtube.com/watch?v=..." --genre "Minimal Techno"

# 🔥 Modalità DropSoul (Hi-Fi P2P + Spectrogram Quality Gate >20kHz)
python3 drop_agent.py "https://www.youtube.com/watch?v=..." --genre "Deep House" --mode dropsoul

# Ispezione Coda Cloud / Pending Hunts
python3 drop_agent.py --dropsoul-queue

# Con lista tracce custom fornita da file
python3 drop_agent.py "https://www.youtube.com/watch?v=..." --genre "Deep House" --tracks-file /path/to/tracks.txt
```

---

## 📁 Struttura Cartelle
- `drop_agent.py`: Pipeline principale orchestrata (`--mode drops` vs `--mode dropsoul`).
- `dropsoul/`: Motore Hi-Fi P2P (client `slskd`, FFT `quality_verifier.py`, `queue_manager.py`, `engine.py`).
- `DROPSOUL_UX_SPEC.md`: Specifiche UX e componenti Frontend per la curation UI.
- `downloader.py`: Downloader yt-dlp / FFmpeg a 320k con artwork, tag e routing DropSoul.
- `enrichment/`: Arricchimento metadati con Discogs, Beatport e copertine HD.
- `harmonic_analyzer.py`: Rilevamento tonalità musicale, Camelot Wheel (8A, 11B) e BPM.
- `exporters/`: Generatore di CUE sheet, playlist m3u8, e formati Rekordbox/Traktor.
- `data/audio/`: Cartella di destinazione delle release curate.
