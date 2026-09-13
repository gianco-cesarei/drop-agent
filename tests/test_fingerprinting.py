#!/usr/bin/env python3
"""
Unit Tests for Audio Fingerprinting, Sliding-Window & Transition Detection (Milestone 1).
"""

import unittest
import numpy as np
import os
import sys

# Ensure drops-agent is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fingerprinting.transition_detector import find_zero_crossing, TransitionDetector
from fingerprinting.audio_fingerprinter import (
    AudioFingerprinter,
    format_timestamp,
    normalize_text_for_comparison,
    are_tracks_similar,
)


class TestFingerprinting(unittest.TestCase):

    def setUp(self):
        self.detector = TransitionDetector(sample_rate=22050)
        self.fingerprinter = AudioFingerprinter(concurrency_limit=2, hop_seconds=60.0)

    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(0), "00:00")
        self.assertEqual(format_timestamp(75), "01:15")
        self.assertEqual(format_timestamp(3665), "01:01:05")

    def test_find_zero_crossing(self):
        # Create a simple sine wave crossing zero at sample 50
        x = np.linspace(-np.pi, np.pi, 100, dtype=np.float32)
        sine = np.sin(x)
        # Target index 48 should snap to closest zero crossing (index 50)
        zc = find_zero_crossing(sine, target_idx=48, search_radius=10)
        self.assertTrue(abs(zc - 50) <= 2)

    def test_spectral_flux_and_rms(self):
        # Synthetic audio: 1 sec 440Hz sine followed by 1 sec noise
        sr = 22050
        t = np.linspace(0, 2, 2 * sr, dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t)
        audio[sr:] += np.random.normal(0, 0.5, sr).astype(np.float32)

        flux, fps = self.detector.compute_spectral_flux(audio)
        rms = self.detector.compute_rms_energy(audio)

        self.assertGreater(len(flux), 0)
        self.assertGreater(len(rms), 0)
        self.assertGreater(fps, 0)

    def test_normalize_and_similarity(self):
        t1 = {"artist": "Adrien Calvet", "title": "Summer of 05 (Original Mix)"}
        t2 = {"artist": "Adrien Calvet", "title": "Summer of 05"}
        t3 = {"artist": "Binh", "title": "Eastern Bloc"}

        self.assertTrue(are_tracks_similar(t1, t2))
        self.assertFalse(are_tracks_similar(t1, t3))

    def test_parse_shazam_payload(self):
        payload = {
            "track": {
                "title": "Breakin' It Down",
                "subtitle": "Petalpusher feat. Ledisi",
                "genres": {"primary": "Deep House"},
                "sections": [
                    {
                        "type": "SONG",
                        "metadata": [{"title": "Album", "text": "Naked Music"}]
                    }
                ],
                "images": {"coverarthq": "https://example.com/cover.jpg"},
                "isrc": "US1234567890",
                "key": "12345"
            }
        }
        parsed = self.fingerprinter.parse_shazam_payload(payload)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["title"], "Breakin' It Down")
        self.assertEqual(parsed["artist"], "Petalpusher feat. Ledisi")
        self.assertEqual(parsed["genre"], "Deep House")
        self.assertEqual(parsed["album"], "Naked Music")
        self.assertEqual(parsed["cover_url"], "https://example.com/cover.jpg")
        self.assertEqual(parsed["isrc"], "US1234567890")

    def test_cluster_and_deduplicate(self):
        track_a = {"artist": "Artist A", "title": "Track 1", "album": "", "genre": "House", "isrc": "", "shazam_id": "1", "cover_url": "", "confidence": 0.95}
        track_b = {"artist": "Artist B", "title": "Track 2", "album": "", "genre": "House", "isrc": "", "shazam_id": "2", "cover_url": "", "confidence": 0.95}

        # Simulated sliding window detections: 0s, 60s, 120s -> Track A; 180s, 240s -> Track B
        raw_detections = [
            (0.0, track_a),
            (60.0, track_a),
            (120.0, track_a),
            (180.0, track_b),
            (240.0, track_b)
        ]

        clustered = self.fingerprinter.cluster_and_deduplicate(
            raw_detections=raw_detections,
            audio_path="/non/existent/path.mp3",
            total_duration=360.0
        )

        self.assertEqual(len(clustered), 2)
        self.assertEqual(clustered[0]["title"], "Track 1")
        self.assertEqual(clustered[0]["track_num"], 1)
        self.assertEqual(clustered[0]["start_time"], 0.0)

        self.assertEqual(clustered[1]["title"], "Track 2")
        self.assertEqual(clustered[1]["track_num"], 2)
        self.assertGreater(clustered[1]["start_time"], 100.0)


if __name__ == '__main__':
    unittest.main()
