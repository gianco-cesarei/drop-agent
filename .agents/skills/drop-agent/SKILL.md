---
name: drop-agent
description: Autonomous Music Curator and High-Quality Downloader for Drops. Extracts full DJ sets, parses tracklists, downloads individual tracks at 320kbps MP3 with full ID3 metadata and cover art, and organizes them into curated genre folders in data/audio.
---

# Drop Agent — Autonomous Music Curator & Ingestion Engine

Drop Agent is the specialized Drops ingestion agent designed to curate, download, tag, and organize electronic music releases, DJ sets, and compilations from YouTube and audio sources.

## Features
1. **Full Set Ingestion**: Downloads the continuous mix at maximum audio quality (320kbps MP3 / FLAC) with embedded artwork and album tags.
2. **AI & Automated Tracklist Recognition**: Automatically identifies individual tracks from YouTube descriptions, comments, or chapter markers, or accepts an LLM-supplied tracklist.
3. **DropSoul Hi-Fi Engine**: Integrates with Soulseek P2P (`slskd`) and FFT audio spectrogram verification (>20kHz cutoff) to prevent fake 128k transcode upscales.
4. **Curator Decision Gate**: Supports Downsizing (temporary WebRip + cloud auto-upgrade), Pure Quality Wait (queued 24/7 in cloud), and Skip.
5. **Individual Track Archiving**: Finds and downloads clean individual full-length track releases for each track in the mix, with full ID3 tags (Artist, Title, Album, Genre, Year, Track Number).
6. **Drops Curation Taxonomy**: Categorizes and organizes folders in `data/audio/<Curated Genre / Compilation Name>/` with generated `.m3u8` playlists and `TRACKLIST.md` metadata files.

## Usage

### Run via Command Line (Standard Fast Drops Mode)
```bash
python3 drop_agent.py "https://www.youtube.com/watch?v=..." --genre "Deep House" --folder "Nude Dimensions Vol 1 (Naked Music 1999) - Deep House"
```

### Run via DropSoul Mode (Audiophile Club Quality & P2P)
```bash
python3 drop_agent.py "https://www.youtube.com/watch?v=..." --genre "Deep House" --mode dropsoul
```

### Check Background Hunts & Cloud Queue
```bash
python3 drop_agent.py --dropsoul-queue
```

### With Custom Tracklist File
```bash
python3 drop_agent.py "https://www.youtube.com/watch?v=..." --genre "Deep House" --tracks-file /path/to/tracks.txt
```
