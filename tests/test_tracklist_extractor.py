#!/usr/bin/env python3
"""
Unit Tests for Tracklist Extractor with Text & Blind Detection Integration.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tracklist_extractor import parse_track_line, extract_tracklist_from_text, extract_or_fingerprint


class TestTracklistExtractor(unittest.TestCase):

    def test_parse_track_line_various_formats(self):
        # Format 1: Numbered with quotes
        l1 = '1. Petalpusher feat. Ledisi – "Breakin\' It Down (Jay\'s Naked Vocal)"'
        p1 = parse_track_line(l1)
        self.assertIsNotNone(p1)
        self.assertEqual(p1["track_num"], 1)
        self.assertEqual(p1["artist"], "Petalpusher feat. Ledisi")
        self.assertIn("Breakin' It Down", p1["title"])

        # Format 2: Leading 0, dash separator
        l2 = "02 - Miguel Migs - Take Me To Paradise (Summer Lover's Dub)"
        p2 = parse_track_line(l2)
        self.assertIsNotNone(p2)
        self.assertEqual(p2["track_num"], 2)
        self.assertEqual(p2["artist"], "Miguel Migs")
        self.assertIn("Take Me To Paradise", p2["title"])

        # Format 3: Timestamp prefix
        l3 = '[04:20] Janet Rushmore - On My Own (Acapella Mix)'
        p3 = parse_track_line(l3)
        self.assertIsNotNone(p3)
        self.assertEqual(p3["artist"], "Janet Rushmore")
        self.assertIn("On My Own", p3["title"])

    def test_extract_tracklist_from_text(self):
        desc = """1. Blue Boy - Remember Me
2. St Germain - Rose Rouge
3. Moodymann - I Can't Kick This Feelin When It Hits"""
        tracks = extract_tracklist_from_text(desc)
        self.assertEqual(len(tracks), 3)
        self.assertEqual(tracks[0]["artist"], "Blue Boy")
        self.assertEqual(tracks[0]["title"], "Remember Me")
        self.assertEqual(tracks[1]["artist"], "St Germain")
        self.assertEqual(tracks[2]["artist"], "Moodymann")

    def test_extract_or_fingerprint_with_text(self):
        desc = """1. Blue Boy - Remember Me
2. St Germain - Rose Rouge
3. Moodymann - I Can't Kick This Feelin"""
        tracks = extract_or_fingerprint(text=desc, audio_path=None)
        self.assertEqual(len(tracks), 3)


if __name__ == '__main__':
    unittest.main()
