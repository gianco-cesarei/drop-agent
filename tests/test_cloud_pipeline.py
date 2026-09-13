"""
Unit tests for Milestone 4: Cloudflare R2 Uploader and Supabase PostgREST Sync Pipeline.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cloud.models import DJSetModel, TrackModel, SetTrackModel, IngestionReport
from cloud.r2_uploader import R2Uploader, _slug_segment
from cloud.supabase_sync import SupabaseSyncClient


class TestR2Uploader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.uploader = R2Uploader(
            account_id="fake_account",
            access_key_id="fake_access",
            secret_access_key="fake_secret",
            bucket="test-drops-bucket",
            public_url="https://audio.drops.live",
            dry_run=True
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_slug_segment(self):
        self.assertEqual(_slug_segment("Deep House / Minimal"), "Deep House - Minimal")
        self.assertEqual(_slug_segment("Artist (Live & Direct)"), "Artist (Live & Direct)")
        self.assertEqual(_slug_segment(None, fallback="default"), "default")

    def test_build_object_key(self):
        key = self.uploader.build_object_key(
            category="Deep House",
            folder_name="Summer Sessions 2026",
            filename="01. Artist - Track.mp3"
        )
        self.assertEqual(key, "Deep House/Summer Sessions 2026/01. Artist - Track.mp3")

    def test_mime_type_detection(self):
        self.assertEqual(self.uploader.detect_mime_type("track.mp3"), "audio/mpeg")
        self.assertEqual(self.uploader.detect_mime_type("cover.jpg"), "image/jpeg")
        self.assertEqual(self.uploader.detect_mime_type("cover.jpeg"), "image/jpeg")
        self.assertEqual(self.uploader.detect_mime_type("cover.png"), "image/png")
        self.assertEqual(self.uploader.detect_mime_type("playlist.m3u8"), "application/vnd.apple.mpegurl")

    def test_upload_file_dry_run(self):
        test_file = os.path.join(self.temp_dir, "test.mp3")
        with open(test_file, "wb") as f:
            f.write(b"dummy audio content")

        url = self.uploader.upload_file(test_file, "audio/test.mp3")
        self.assertEqual(url, "https://audio.drops.live/audio/test.mp3")


class TestSupabaseSyncClient(unittest.TestCase):
    def setUp(self):
        self.client = SupabaseSyncClient(
            supabase_url="https://xyz.supabase.co",
            supabase_key="fake_key",
            dry_run=True
        )

    def test_models_validation(self):
        dj_set = DJSetModel(
            title="Vinyl Sessions Vol 1",
            source_url="https://youtube.com/watch?v=12345",
            genre="Deep House",
            duration_seconds=3600.0,
            average_bpm=124.0,
            initial_key="8A"
        )
        self.assertEqual(dj_set.title, "Vinyl Sessions Vol 1")
        self.assertEqual(dj_set.initial_key, "8A")

        track = TrackModel(
            title="Summer of 05",
            artist="Adrien Calvet",
            record_label="Sahko",
            catalog_number="SAHKO01",
            bpm=124.0,
            camelot_key="8A"
        )
        self.assertEqual(track.artist, "Adrien Calvet")
        self.assertEqual(track.catalog_number, "SAHKO01")

    def test_sync_full_release_dry_run(self):
        dj_set = DJSetModel(
            title="Vinyl Sessions Vol 1",
            source_url="https://youtube.com/watch?v=12345",
            genre="Deep House"
        )
        tracks = [
            TrackModel(title="Track 1", artist="Artist 1", bpm=124.0, camelot_key="8A"),
            TrackModel(title="Track 2", artist="Artist 2", bpm=125.0, camelot_key="9A"),
        ]
        set_tracks = [
            SetTrackModel(set_id="", track_number=1, artist="Artist 1", title="Track 1"),
            SetTrackModel(set_id="", track_number=2, artist="Artist 2", title="Track 2"),
        ]

        report = self.client.sync_full_release(dj_set, tracks, set_tracks)
        self.assertTrue(report.success)
        self.assertIsNotNone(report.synced_set_id)
        self.assertEqual(len(report.synced_track_ids), 2)


if __name__ == "__main__":
    unittest.main()
