"""
Audio Quality Verifier & Spectrogram Frequency Cutoff Analyzer.
Detects fake/upscaled 320kbps MP3s and lossy transcodes using FFT spectral analysis.
"""

from __future__ import annotations

import os
import json
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import numpy as np


class QualityVerdict(str, Enum):
    VERIFIED_HQ = "VERIFIED_HQ"                  # Cutoff >= 20.0 kHz (True 320k or Lossless/FLAC)
    ACCEPTABLE_192K = "ACCEPTABLE_192K"          # Cutoff ~18.5 - 19.5 kHz (192k-256k real)
    SUSPECT_FAKE_128K = "SUSPECT_FAKE_128K"      # Sharp cutoff <= 16.5 kHz (Fake 320k upscaled from 128k)
    WEBRIP_TRANSCODE = "WEBRIP_TRANSCODE"        # Typical YouTube/Opus 128-160k lossy profile
    ANALYSIS_ERROR = "ANALYSIS_ERROR"


@dataclass
class QualityReport:
    is_genuine: bool
    verdict: QualityVerdict
    cutoff_frequency_hz: float
    nominal_bitrate_kbps: Optional[int]
    sample_rate_hz: int
    format: str
    spectrogram_image_path: Optional[str] = None
    details: str = ""

    def summary(self) -> str:
        icon = "✅" if self.is_genuine else "⚠️"
        return (
            f"{icon} [{self.verdict.value}] Cutoff: {self.cutoff_frequency_hz:.1f} Hz | "
            f"Nominal: {self.nominal_bitrate_kbps or '?'} kbps ({self.format.upper()}) - {self.details}"
        )


class AudioQualityVerifier:
    def __init__(
        self,
        hq_threshold_hz: float = 19500.0,
        fake_128k_threshold_hz: float = 16500.0,
        ffmpeg_bin: Optional[str] = None,
        ffprobe_bin: Optional[str] = None,
    ):
        self.hq_threshold_hz = hq_threshold_hz
        self.fake_128k_threshold_hz = fake_128k_threshold_hz
        self.ffmpeg_bin = ffmpeg_bin or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
        self.ffprobe_bin = ffprobe_bin or shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

    def get_audio_metadata(self, file_path: str) -> Tuple[Optional[int], int, str, float]:
        """Returns (nominal_bitrate_kbps, sample_rate, format, duration_seconds)."""
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=bit_rate,format_name,duration:stream=sample_rate,bit_rate",
            "-of", "json",
            file_path,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(res.stdout)
            format_info = info.get("format", {})
            streams = info.get("streams", [])
            stream_info = streams[0] if streams else {}

            bit_rate = stream_info.get("bit_rate") or format_info.get("bit_rate")
            nominal_bitrate = int(int(bit_rate) / 1000) if bit_rate else None
            sample_rate = int(stream_info.get("sample_rate", 44100))
            fmt = format_info.get("format_name", "unknown").split(",")[0]
            duration = float(format_info.get("duration", 0.0))
            return nominal_bitrate, sample_rate, fmt, duration
        except Exception:
            return None, 44100, "unknown", 0.0

    def analyze(
        self,
        file_path: str,
        generate_spectrogram: bool = False,
        spectrogram_out_dir: Optional[str] = None,
    ) -> QualityReport:
        """
        Extracts a representative audio slice, computes FFT frequency response,
        and determines if the file is genuine high quality or an upscaled fake.
        """
        if not os.path.exists(file_path):
            return QualityReport(
                is_genuine=False,
                verdict=QualityVerdict.ANALYSIS_ERROR,
                cutoff_frequency_hz=0.0,
                nominal_bitrate_kbps=None,
                sample_rate_hz=44100,
                format="none",
                details=f"File not found: {file_path}",
            )

        nominal_bitrate, sample_rate, fmt, duration = self.get_audio_metadata(file_path)

        # Choose a 30s slice from ~25% into the track to avoid silent intros
        offset = max(10.0, duration * 0.25) if duration > 30 else 0.0
        slice_len = 30.0 if duration > 40 else max(5.0, duration)

        target_sr = 44100
        cmd = [
            self.ffmpeg_bin,
            "-v", "error",
            "-ss", str(offset),
            "-t", str(slice_len),
            "-i", file_path,
            "-f", "s16le",
            "-ac", "1",
            "-ar", str(target_sr),
            "-",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, check=True)
            raw_audio = proc.stdout
        except Exception as e:
            return QualityReport(
                is_genuine=False,
                verdict=QualityVerdict.ANALYSIS_ERROR,
                cutoff_frequency_hz=0.0,
                nominal_bitrate_kbps=nominal_bitrate,
                sample_rate_hz=sample_rate,
                format=fmt,
                details=f"FFmpeg decode error: {e}",
            )

        if len(raw_audio) < 44100 * 2 * 2:  # at least 2 seconds
            return QualityReport(
                is_genuine=False,
                verdict=QualityVerdict.ANALYSIS_ERROR,
                cutoff_frequency_hz=0.0,
                nominal_bitrate_kbps=nominal_bitrate,
                sample_rate_hz=sample_rate,
                format=fmt,
                details="Audio sample too short for spectral evaluation",
            )

        samples = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)

        # Windowed STFT-like averaging
        n_fft = 4096
        hop_size = 2048
        window = np.hanning(n_fft)

        num_frames = (len(samples) - n_fft) // hop_size
        if num_frames <= 0:
            num_frames = 1
            samples = np.pad(samples, (0, max(0, n_fft - len(samples))))

        accumulated_mag = np.zeros(n_fft // 2 + 1, dtype=np.float64)
        for i in range(min(num_frames, 200)):
            start = i * hop_size
            frame = samples[start : start + n_fft] * window
            fft_res = np.abs(np.fft.rfft(frame))
            accumulated_mag += fft_res

        mean_mag = accumulated_mag / max(1, min(num_frames, 200))
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / target_sr)

        # Convert to relative dB scale
        max_val = np.max(mean_mag)
        if max_val <= 1e-9:
            cutoff = 0.0
        else:
            mag_db = 20.0 * np.log10(mean_mag / max_val + 1e-9)
            
            # Find cutoff: search from Nyquist downwards (e.g. from 21.5kHz down)
            # Find frequency where audio energy is sustained above noise floor (-55 dB relative)
            noise_threshold_db = -58.0
            
            # Look above 12 kHz to find the upper bound
            high_idx = np.where((freqs >= 12000) & (freqs <= 22050))[0]
            cutoff = 12000.0
            if len(high_idx) > 0:
                # Find the highest frequency with meaningful energy
                active_high = high_idx[mag_db[high_idx] >= noise_threshold_db]
                if len(active_high) > 0:
                    cutoff = float(freqs[active_high[-1]])
                else:
                    cutoff = 12000.0

        # Generate PNG spectrogram if requested
        img_path = None
        if generate_spectrogram:
            out_dir = spectrogram_out_dir or os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            img_path = os.path.join(out_dir, f"{base_name}_spectrogram.png")
            spec_cmd = [
                self.ffmpeg_bin,
                "-v", "error",
                "-y",
                "-ss", str(offset),
                "-t", "30",
                "-i", file_path,
                "-lavfi", "showspectrumpic=s=1024x512:legend=1:color=magma",
                img_path,
            ]
            try:
                subprocess.run(spec_cmd, check=True)
            except Exception:
                img_path = None

        # Determine Verdict
        is_genuine = False
        if cutoff >= self.hq_threshold_hz:
            verdict = QualityVerdict.VERIFIED_HQ
            is_genuine = True
            details = "Verified studio/club audio quality with full high-frequency extension."
        elif cutoff >= 18000.0:
            verdict = QualityVerdict.ACCEPTABLE_192K
            is_genuine = (nominal_bitrate or 0) <= 256
            details = "Moderate cutoff around 18-19 kHz. Acceptable high-bitrate encoding."
        elif cutoff <= self.fake_128k_threshold_hz:
            verdict = QualityVerdict.SUSPECT_FAKE_128K
            is_genuine = False
            details = f"Sharp brick-wall cutoff at ~{cutoff:.0f} Hz indicates upscaled 128k lossy transcode."
        else:
            verdict = QualityVerdict.WEBRIP_TRANSCODE
            is_genuine = False
            details = f"Lossy cutoff at ~{cutoff:.0f} Hz characteristic of standard WebRip/YouTube compression."

        return QualityReport(
            is_genuine=is_genuine,
            verdict=verdict,
            cutoff_frequency_hz=cutoff,
            nominal_bitrate_kbps=nominal_bitrate,
            sample_rate_hz=sample_rate,
            format=fmt,
            spectrogram_image_path=img_path,
            details=details,
        )
