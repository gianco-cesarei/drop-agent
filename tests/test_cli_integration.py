"""
Integration tests for Drop Agent CLI Master Orchestrator.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from drop_agent import run_drop_agent, create_m3u_playlist, create_tracklist_md
from downloader import DropDownloader
from enrichment.discogs_client import DiscogsClient
from enrichment.beatport_client import BeatportClient


class TestDropAgentCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_m3u_playlist(self):
        # Create dummy mp3 files
        for i in range(1, 4):
            with open(os.path.join(self.temp_dir, f"0{i}. Artist - Track {i}.mp3"), "w") as f:
                f.write("dummy")

        playlist_path = create_m3u_playlist(self.temp_dir, "Test_Release")
        self.assertTrue(os.path.exists(playlist_path))
        with open(playlist_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("#EXTM3U", content)
            self.assertIn("01. Artist - Track 1.mp3", content)
            self.assertIn("02. Artist - Track 2.mp3", content)

    def test_create_tracklist_md(self):
        analyzed_tracks = [
            {
                "track_num": 1,
                "artist": "Adrien Calvet",
                "title": "Summer of 05",
                "key": "A minor",
                "camelot": "8A",
                "bpm": 124.0,
                "record_label": "Sahko",
                "catalog_number": "SAHKO01",
                "discogs_url": "https://discogs.com/test",
                "beatport_url": "https://beatport.com/test"
            }
        ]
        md_file = create_tracklist_md(
            directory=self.temp_dir,
            album_title="Deep House Set",
            genre="Deep House",
            url="https://youtube.com/watch?v=12345",
            analyzed_tracks=analyzed_tracks,
            r2_base_url="https://audio.drops.live"
        )
        self.assertTrue(os.path.exists(md_file))
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("# Deep House Set", content)
            self.assertIn("Adrien Calvet", content)
            self.assertIn("8A", content)
            self.assertIn("SAHKO01", content)
            self.assertIn("Discogs", content)
            self.assertIn("Beatport", content)

    @patch("drop_agent.estimate_key", return_value=("A minor", "8A"))
    @patch("drop_agent.estimate_bpm", return_value=124.0)
    @patch.object(DiscogsClient, "search_release")
    @patch.object(BeatportClient, "search_track")
    @patch.object(DropDownloader, "get_video_info")
    @patch.object(DropDownloader, "download_full_mix")
    @patch.object(DropDownloader, "download_single_track")
    def test_run_drop_agent_pipeline_dry_run(
        self,
        mock_download_single,
        mock_download_full,
        mock_get_info,
        mock_beatport,
        mock_discogs,
        mock_bpm,
        mock_key
    ):
        mock_get_info.return_value = {
            "title": "Minimal Deep Sessions 2026",
            "description": "01. Adrien Calvet - Summer of 05\n02. Binh - Eastern Bloc",
            "duration": 3600
        }
        mock_discogs.return_value = {
            "label": "Sahko Recordings",
            "catalog_number": "SAHKO01",
            "release_year": "2020",
            "discogs_url": "https://discogs.com/release/123",
            "cover_image_url": None
        }
        mock_beatport.return_value = {
            "buy_url": "https://beatport.com/track/123",
            "bpm": 124.0,
            "key": "8A"
        }
        
        # Create dummy mp3 outputs for downloader
        dummy_mp3_1 = os.path.join(self.temp_dir, "01. Adrien Calvet - Summer of 05.mp3")
        dummy_mp3_2 = os.path.join(self.temp_dir, "02. Binh - Eastern Bloc.mp3")
        with open(dummy_mp3_1, "wb") as f: f.write(b"\xff\xfb\x90\x44" + b"\x00" * 1024)
        with open(dummy_mp3_2, "wb") as f: f.write(b"\xff\xfb\x90\x44" + b"\x00" * 1024)

        mock_download_full.return_value = os.path.join(self.temp_dir, "00. Full Mix.mp3")
        mock_download_single.side_effect = [dummy_mp3_1, dummy_mp3_2]

        result = run_drop_agent(
            url="https://youtube.com/watch?v=test",
            genre="Minimal",
            audio_root=self.temp_dir,
            skip_full_mix=True,
            enrich_metadata=True,
            upload_cloud=True,
            sync_db=True,
            dry_run=True
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["downloaded_count"], 2)
        self.assertTrue(os.path.exists(result["target_dir"]))


if __name__ == "__main__":
    unittest.main()
