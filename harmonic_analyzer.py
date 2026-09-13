#!/usr/bin/env python3
"""
Harmonic Key & BPM Analyzer for Drop Agent.
Calculates and maps Musical Keys to Camelot Wheel notation (e.g. 8A, 8B, 4A, etc.)
and estimates BPM & Key using audio FFT/Chromagram analysis via ffmpeg and numpy.
"""

import os
import subprocess
import numpy as np
from typing import Dict, Tuple, Optional


# Camelot Wheel Mapping Table
# Standard DJ notation used by Mixed In Key, Rekordbox, Traktor, Engine DJ
KEY_TO_CAMELOT = {
    # Minor Keys (A)
    "Abm": "1A", "G#m": "1A", "G# minor": "1A", "Ab minor": "1A",
    "Ebm": "2A", "D#m": "2A", "Eb minor": "2A", "D# minor": "2A",
    "Bbm": "3A", "A#m": "3A", "Bb minor": "3A", "A# minor": "3A",
    "Fm": "4A", "F minor": "4A",
    "Cm": "5A", "C minor": "5A",
    "Gm": "6A", "G minor": "6A",
    "Dm": "7A", "D minor": "7A",
    "Am": "8A", "A minor": "8A",
    "Em": "9A", "E minor": "9A",
    "Bm": "10A", "B minor": "10A",
    "F#m": "11A", "Gbm": "11A", "F# minor": "11A", "Gb minor": "11A",
    "C#m": "12A", "Dbm": "12A", "C# minor": "12A", "Db minor": "12A",

    # Major Keys (B)
    "B": "1B", "B maj": "1B", "B major": "1B",
    "F#": "2B", "Gb": "2B", "F# major": "2B", "Gb major": "2B",
    "Db": "3B", "C#": "3B", "Db major": "3B", "C# major": "3B",
    "Ab": "4B", "G#": "4B", "Ab major": "4B", "G# major": "4B",
    "Eb": "5B", "D#": "5B", "Eb major": "5B", "D# major": "5B",
    "Bb": "6B", "A#": "6B", "Bb major": "6B", "A# major": "6B",
    "F": "7B", "F major": "7B",
    "C": "8B", "C major": "8B",
    "G": "9B", "G major": "9B",
    "D": "10B", "D major": "10B",
    "A": "11B", "A major": "11B",
    "E": "12B", "E major": "12B"
}

# Pitch profiles for Krumhansl-Schmuckler Key-Finding Algorithm
PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def extract_raw_audio(file_path: str, sample_rate: int = 22050, duration: int = 60, offset: int = 30) -> Optional[np.ndarray]:
    """Extracts a segment of mono PCM float32 audio using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-ss", str(offset),
        "-t", str(duration),
        "-i", file_path,
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "f32le",
        "-v", "quiet",
        "pipe:1"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        samples = np.frombuffer(proc.stdout, dtype=np.float32)
        return samples
    except Exception as e:
        print(f"[Harmonic Analyzer] Error reading audio: {e}")
        return None


def estimate_key(file_path: str) -> Tuple[str, str]:
    """
    Estimates the musical key and Camelot code using Chromagram profile correlation.
    Returns: (Musical Key, Camelot Key) e.g. ("A minor", "8A")
    """
    samples = extract_raw_audio(file_path, sample_rate=22050, duration=60, offset=30)
    if samples is None or len(samples) < 22050:
        return "Unknown", "Unknown"

    # Compute FFT magnitude spectrum
    window_size = 4096
    hop_size = 2048
    chroma = np.zeros(12)

    # Reference pitch A4 = 440 Hz
    frequencies = np.fft.rfftfreq(window_size, 1.0 / 22050)
    # Map frequency bins to pitch class 0..11 (C..B)
    valid_freqs = (frequencies >= 65.4) & (frequencies <= 2093.0)  # C2 to C7
    pitch_classes = np.zeros(len(frequencies), dtype=int)
    for i, f in enumerate(frequencies):
        if valid_freqs[i]:
            midi = 69 + 12 * np.log2(f / 440.0)
            pitch_classes[i] = int(round(midi)) % 12

    for start in range(0, len(samples) - window_size, hop_size):
        frame = samples[start:start + window_size] * np.hanning(window_size)
        spec = np.abs(np.fft.rfft(frame))
        for p in range(12):
            mask = valid_freqs & (pitch_classes == p)
            chroma[p] += np.sum(spec[mask])

    if np.sum(chroma) == 0:
        return "Unknown", "Unknown"

    chroma = chroma / np.linalg.norm(chroma)

    # Correlate with all 24 major/minor keys
    best_corr = -1.0
    best_key = "C major"
    is_minor = False

    for shift in range(12):
        # Major
        shifted_maj = np.roll(MAJOR_PROFILE, shift)
        shifted_maj = shifted_maj / np.linalg.norm(shifted_maj)
        corr_maj = np.dot(chroma, shifted_maj)
        if corr_maj > best_corr:
            best_corr = corr_maj
            best_key = f"{PITCH_NAMES[shift]} major"

        # Minor
        shifted_min = np.roll(MINOR_PROFILE, shift)
        shifted_min = shifted_min / np.linalg.norm(shifted_min)
        corr_min = np.dot(chroma, shifted_min)
        if corr_min > best_corr:
            best_corr = corr_min
            best_key = f"{PITCH_NAMES[shift]} minor"

    camelot = KEY_TO_CAMELOT.get(best_key, "Unknown")
    return best_key, camelot


def estimate_bpm(file_path: str) -> float:
    """
    Estimates track BPM using spectral flux onset autocorrelation.
    """
    samples = extract_raw_audio(file_path, sample_rate=22050, duration=45, offset=45)
    if samples is None or len(samples) < 22050:
        return 124.0

    # Onset envelope via spectral difference
    window_size = 1024
    hop_size = 512
    num_frames = (len(samples) - window_size) // hop_size
    prev_spec = np.zeros(window_size // 2 + 1)
    onsets = np.zeros(num_frames)

    for i in range(num_frames):
        start = i * hop_size
        frame = samples[start:start + window_size] * np.hanning(window_size)
        spec = np.abs(np.fft.rfft(frame))
        diff = spec - prev_spec
        onsets[i] = np.sum(diff[diff > 0])
        prev_spec = spec

    # Autocorrelation of onsets
    onsets -= np.mean(onsets)
    corr = np.correlate(onsets, onsets, mode="full")
    corr = corr[len(corr) // 2:]

    # Focus BPM range 115 - 135 for Deep House / House
    fps = 22050 / hop_size  # ~43.06 frames/sec
    min_lag = int(fps * 60 / 140)  # ~18 frames (140 BPM)
    max_lag = int(fps * 60 / 110)  # ~23 frames (110 BPM)

    if max_lag < len(corr):
        search_window = corr[min_lag:max_lag]
        if len(search_window) > 0 and np.max(search_window) > 0:
            peak_lag = min_lag + np.argmax(search_window)
            bpm = (fps * 60) / peak_lag
            return round(bpm, 1)

    return 124.0
