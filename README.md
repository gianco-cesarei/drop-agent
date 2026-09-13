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

# Con lista tracce custom fornita da file
python3 drop_agent.py "https://www.youtube.com/watch?v=..." --genre "Deep House" --tracks-file /path/to/tracks.txt
```

---

## 📁 Struttura Cartelle
- `drop_agent.py`: Pipeline principale orchestrata.
- `downloader.py`: Downloader yt-dlp / FFmpeg a 320k con artwork e tag.
- `enrichment/`: Arricchimento metadati con Discogs, Beatport e copertine HD.
- `harmonic_analyzer.py`: Rilevamento tonalità musicale, Camelot Wheel (8A, 11B) e BPM.
- `exporters/`: Generatore di CUE sheet, playlist m3u8, e formati Rekordbox/Traktor.
- `data/audio/`: Cartella di destinazione delle release curate.
