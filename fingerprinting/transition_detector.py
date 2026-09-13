#!/usr/bin/env python3
"""
Transition & Beat Drop Detector for Drop Agent.
Analyzes audio spectral flux, RMS energy dips/rises, and zero-crossing points
to pinpoint precise DJ mixing transitions and beat drop cue points.
"""

import subprocess
import numpy as np
from typing import Tuple, Optional


def find_zero_crossing(samples: np.ndarray, target_idx: int, search_radius: int = 1000) -> int:
    """
    Finds the index closest to target_idx where the audio waveform crosses zero (y[i] * y[i+1] <= 0).
    Avoids audio clicks / DC offset pops during slicing.
    """
    if len(samples) < 2:
        return target_idx

    start = max(0, target_idx - search_radius)
    end = min(len(samples) - 1, target_idx + search_radius)

    sub = samples[start:end]
    # Check where sign changes
    signs = np.sign(sub)
    # Replace 0 with 1 to detect exact zeros
    signs[signs == 0] = 1
    zero_crossings = np.where(np.diff(signs) != 0)[0] + start

    if len(zero_crossings) == 0:
        # Fallback to minimum absolute amplitude
        return int(start + np.argmin(np.abs(sub)))

    closest_idx = zero_crossings[np.argmin(np.abs(zero_crossings - target_idx))]
    return int(closest_idx)


class TransitionDetector:
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate

    def extract_audio_region(
        self, audio_path: str, offset_sec: float, duration_sec: float
    ) -> Optional[np.ndarray]:
        """Extracts mono float32 audio samples in RAM from audio_path using ffmpeg."""
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", f"{max(0.0, offset_sec):.3f}",
            "-t", f"{duration_sec:.3f}",
            "-i", audio_path,
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "-f", "f32le",
            "-v", "quiet",
            "pipe:1",
        ]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            samples = np.frombuffer(proc.stdout, dtype=np.float32)
            return samples
        except Exception as e:
            print(f"[Transition Detector] ⚠️ Failed extracting audio region: {e}")
            return None

    def compute_spectral_flux(
        self, samples: np.ndarray, hop_size: int = 512, window_size: int = 1024
    ) -> Tuple[np.ndarray, float]:
        """
        Computes half-wave rectified spectral flux across STFT frames.
        Returns: (flux_array, frames_per_second)
        """
        if len(samples) < window_size:
            return np.array([]), 0.0

        num_frames = (len(samples) - window_size) // hop_size
        if num_frames <= 0:
            return np.array([]), 0.0

        fps = self.sample_rate / hop_size
        prev_mag = np.zeros(window_size // 2 + 1)
        flux = np.zeros(num_frames)

        for i in range(num_frames):
            start = i * hop_size
            frame = samples[start:start + window_size] * np.hanning(window_size)
            mag = np.abs(np.fft.rfft(frame))
            diff = mag - prev_mag
            # Half-wave rectification (keep only positive increases in energy)
            flux[i] = np.sum(diff[diff > 0])
            prev_mag = mag

        # Normalize flux
        if np.max(flux) > 0:
            flux = flux / np.max(flux)

        return flux, fps

    def compute_rms_energy(
        self, samples: np.ndarray, hop_size: int = 512, window_size: int = 1024
    ) -> np.ndarray:
        """Computes Root Mean Square (RMS) energy per frame."""
        if len(samples) < window_size:
            return np.array([])

        num_frames = (len(samples) - window_size) // hop_size
        if num_frames <= 0:
            return np.array([])

        rms = np.zeros(num_frames)
        for i in range(num_frames):
            start = i * hop_size
            frame = samples[start:start + window_size]
            rms[i] = np.sqrt(np.mean(frame ** 2) + 1e-12)

        if np.max(rms) > 0:
            rms = rms / np.max(rms)
        return rms

    def detect_transition_point(
        self,
        audio_path: str,
        boundary_start_sec: float,
        boundary_end_sec: float,
    ) -> float:
        """
        Pinpoints the optimal transition / beat drop timestamp within [boundary_start_sec, boundary_end_sec].
        Combines RMS dip/rise and spectral flux onset peaks.
        """
        duration = max(1.0, boundary_end_sec - boundary_start_sec)
        samples = self.extract_audio_region(audio_path, boundary_start_sec, duration)
        if samples is None or len(samples) < 2048:
            # Fallback to midpoint
            return round((boundary_start_sec + boundary_end_sec) / 2.0, 2)

        flux, fps = self.compute_spectral_flux(samples)
        rms = self.compute_rms_energy(samples)

        if len(flux) == 0 or len(rms) == 0:
            return round((boundary_start_sec + boundary_end_sec) / 2.0, 2)

        min_len = min(len(flux), len(rms))
        flux = flux[:min_len]
        rms = rms[:min_len]

        # Transition score: High spectral flux + significant RMS energy onset
        # Score emphasizes sudden energy/spectral jumps (kick in / drop)
        diff_rms = np.diff(rms, prepend=rms[0])
        diff_rms[diff_rms < 0] = 0
        if np.max(diff_rms) > 0:
            diff_rms = diff_rms / np.max(diff_rms)

        combined_score = 0.6 * flux + 0.4 * diff_rms
        best_frame = int(np.argmax(combined_score))
        offset_in_region = best_frame / fps if fps > 0 else (duration / 2.0)

        raw_transition_sec = boundary_start_sec + offset_in_region

        # Snap to nearest zero crossing for clean audio boundary
        aligned_sec = self.align_to_nearest_zero_crossing(audio_path, raw_transition_sec)
        return round(aligned_sec, 2)

    def align_to_nearest_zero_crossing(
        self, audio_path: str, timestamp_sec: float, search_window_sec: float = 0.05
    ) -> float:
        """Snaps a timestamp to the closest zero-crossing point in the audio waveform."""
        half_win = search_window_sec / 2.0
        start_sec = max(0.0, timestamp_sec - half_win)
        samples = self.extract_audio_region(audio_path, start_sec, search_window_sec)
        if samples is None or len(samples) < 2:
            return timestamp_sec

        target_idx = int(half_win * self.sample_rate)
        best_idx = find_zero_crossing(samples, target_idx, search_radius=int(half_win * self.sample_rate))
        delta_sec = (best_idx - target_idx) / self.sample_rate
        return max(0.0, timestamp_sec + delta_sec)
