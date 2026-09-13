#!/usr/bin/env python3
"""
Unit Tests for Smart CUE Splitting & Rekordbox/Traktor Exporters (Milestone 2).
"""

import unittest
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from exporters.cue_generator import (
    seconds_to_cue_time,
    cue_time_to_seconds,
    generate_cue_sheet,
    generate_extended_m3u8,
    generate_rekordbox_xml,
    generate_traktor_nml,
    export_all_dj_formats,
)


class TestExporters(unittest.TestCase):

    def setUp(self):
        self.sample_tracks = [
            {
                "track_num": 1,
                "artist": "Adrien Calvet",
                "title": "Summer of 05",
                "start_time": 0.0,
                "end_time": 385.0,
                "duration_seconds": 385.0,
                "camelot": "8A",
                "bpm": 124.0,
                "filename": "01. Adrien Calvet - Summer of 05.mp3"
            },
            {
                "track_num": 2,
                "artist": "Binh",
                "title": "Eastern Bloc",
                "start_time": 385.25,
                "end_time": 720.0,
                "duration_seconds": 334.75,
                "camelot": "9A",
                "bpm": 125.0,
                "filename": "02. Binh - Eastern Bloc.mp3"
            }
        ]

    def test_cue_time_conversion(self):
        # 0 seconds -> 00:00:00
        self.assertEqual(seconds_to_cue_time(0.0), "00:00:00")
        # 60 seconds -> 01:00:00
        self.assertEqual(seconds_to_cue_time(60.0), "01:00:00")
        # 1.0 second with 37.5 frames (approx 0.5s -> ~37-38 frames)
        self.assertEqual(seconds_to_cue_time(1.5), "00:01:38")
        # Round trip
        t = 385.25
        cue_str = seconds_to_cue_time(t)
        back_t = cue_time_to_seconds(cue_str)
        self.assertAlmostEqual(t, back_t, delta=0.02)

    def test_generate_cue_sheet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cue_file = os.path.join(tmpdir, "test_set.cue")
            content = generate_cue_sheet(
                album_title="Deep House Sessions",
                performer="Various Artists",
                genre="Deep House",
                audio_filename="00. Deep House Sessions.mp3",
                tracks=self.sample_tracks,
                output_path=cue_file
            )

            self.assertTrue(os.path.exists(cue_file))
            self.assertIn('TITLE "Deep House Sessions"', content)
            self.assertIn('FILE "00. Deep House Sessions.mp3" MP3', content)
            self.assertIn('TRACK 01 AUDIO', content)
            self.assertIn('TITLE "Summer of 05"', content)
            self.assertIn('PERFORMER "Adrien Calvet"', content)
            self.assertIn('INDEX 01 00:00:00', content)
            self.assertIn('TRACK 02 AUDIO', content)
            self.assertIn('INDEX 01 06:25:19', content)

    def test_generate_extended_m3u8(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            m3u_file = os.path.join(tmpdir, "test_set.m3u8")
            content = generate_extended_m3u8(
                playlist_name="Deep House Sessions",
                tracks=self.sample_tracks,
                output_path=m3u_file
            )

            self.assertTrue(os.path.exists(m3u_file))
            self.assertIn("#EXTM3U", content)
            self.assertIn("#EXTINF:385,Adrien Calvet - Summer of 05", content)
            self.assertIn("#EXT-X-KEY:CAMELOT=8A", content)
            self.assertIn("#EXT-X-BPM:124.0", content)
            self.assertIn("01. Adrien Calvet - Summer of 05.mp3", content)

    def test_generate_rekordbox_xml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_file = os.path.join(tmpdir, "rekordbox.xml")
            fake_audio = os.path.join(tmpdir, "00. mix.mp3")
            with open(fake_audio, 'wb') as f:
                f.write(b"dummy audio content")

            xml_str = generate_rekordbox_xml(
                album_title="Deep House Mix",
                performer="DJ Drops",
                genre="Deep House",
                audio_file_path=fake_audio,
                tracks=self.sample_tracks,
                output_path=xml_file
            )

            self.assertTrue(os.path.exists(xml_file))

            # Validate that the generated XML is well-formed
            root = ET.fromstring(xml_str)
            self.assertEqual(root.tag, "DJ_PLAYLISTS")
            self.assertEqual(root.attrib.get("Version"), "1.0.0")

            product = root.find("PRODUCT")
            self.assertIsNotNone(product)
            self.assertEqual(product.attrib.get("Name"), "rekordbox")

            collection = root.find("COLLECTION")
            self.assertIsNotNone(collection)
            tracks_el = collection.findall("TRACK")
            self.assertGreaterEqual(len(tracks_el), 2)

            # Check full mix position marks / cues
            mix_el = tracks_el[0]
            cues = mix_el.findall("POSITION_MARK")
            self.assertEqual(len(cues), 2)
            self.assertEqual(cues[0].attrib.get("Name"), "01. Adrien Calvet - Summer of 05")
            self.assertEqual(cues[1].attrib.get("Name"), "02. Binh - Eastern Bloc")

            playlists = root.find("PLAYLISTS")
            self.assertIsNotNone(playlists)

    def test_generate_traktor_nml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nml_file = os.path.join(tmpdir, "traktor.nml")
            fake_audio = os.path.join(tmpdir, "00. mix.mp3")
            with open(fake_audio, 'wb') as f:
                f.write(b"dummy audio content")

            nml_str = generate_traktor_nml(
                album_title="Deep House Mix",
                performer="DJ Drops",
                genre="Deep House",
                audio_file_path=fake_audio,
                tracks=self.sample_tracks,
                output_path=nml_file
            )

            self.assertTrue(os.path.exists(nml_file))

            # Validate XML
            root = ET.fromstring(nml_str)
            self.assertEqual(root.tag, "NML")
            self.assertEqual(root.attrib.get("VERSION"), "19")

            collection = root.find("COLLECTION")
            self.assertIsNotNone(collection)
            entry = collection.find("ENTRY")
            self.assertIsNotNone(entry)

            cues = entry.findall("CUE_V2")
            self.assertEqual(len(cues), 2)
            self.assertEqual(cues[0].attrib.get("NAME"), "01. Summer of 05")

    def test_export_all_dj_formats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_file = "00. mix.mp3"
            full_path = os.path.join(tmpdir, audio_file)
            with open(full_path, 'wb') as f:
                f.write(b"dummy audio content")

            res = export_all_dj_formats(
                target_dir=tmpdir,
                album_title="Deep House Test",
                genre="Deep House",
                full_mix_filename=audio_file,
                tracks=self.sample_tracks
            )

            self.assertTrue(os.path.exists(res["cue"]))
            self.assertTrue(os.path.exists(res["m3u8"]))
            self.assertTrue(os.path.exists(res["rekordbox"]))
            self.assertTrue(os.path.exists(res["traktor"]))


if __name__ == '__main__':
    unittest.main()
