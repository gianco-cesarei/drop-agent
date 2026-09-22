"""
Unit Tests for DropSoul Engine & Quality Verifier.
"""

import os
import unittest
import numpy as np

from dropsoul.quality_verifier import AudioQualityVerifier, QualityVerdict
from dropsoul.soulseek_client import SoulseekClient, SoulseekSearchResult
from dropsoul.queue_manager import DropSoulQueueManager, QueueStatus
from dropsoul.engine import DropSoulEngine, DecisionAction


class TestDropSoulComponents(unittest.TestCase):
    def setUp(self):
        self.verifier = AudioQualityVerifier()
        self.queue_mgr = DropSoulQueueManager(local_db_path="data/test_dropsoul_queue.json")

    def tearDown(self):
        if os.path.exists("data/test_dropsoul_queue.json"):
            os.remove("data/test_dropsoul_queue.json")

    def test_soulseek_search_result_scoring(self):
        # FLAC should outscore MP3
        flac_res = SoulseekSearchResult(
            username="djalex",
            filename="track.flac",
            size_bytes=45000000,
            bitrate_kbps=1000,
            sample_rate=44100,
            extension="flac",
            is_lossless=True,
            queue_length=0,
            upload_speed_bps=1000000,
        )
        mp3_res = SoulseekSearchResult(
            username="beatdigger",
            filename="track.mp3",
            size_bytes=12000000,
            bitrate_kbps=320,
            sample_rate=44100,
            extension="mp3",
            is_lossless=False,
            queue_length=5,
            upload_speed_bps=200000,
        )
        self.assertTrue(flac_res.is_lossless)
        self.assertTrue(flac_res.score > mp3_res.score)
        self.assertTrue(mp3_res.is_320k_or_better)

    def test_queue_lifecycle(self):
        item = self.queue_mgr.add_track(
            artist="Kerri Chandler",
            title="Atmospheric Beats",
            album_title="Deep House Classics",
            status=QueueStatus.DOWNSIZED_PLACEHOLDER,
            downsized_file_path="/tmp/placeholder.mp3",
        )
        self.assertEqual(item.status, QueueStatus.DOWNSIZED_PLACEHOLDER)
        
        pending = self.queue_mgr.get_pending_hunts()
        self.assertEqual(len(pending), 1)

        # Upgrade to HQ
        upgraded = self.queue_mgr.mark_completed_hq(
            item_id=item.id,
            hq_file_path="/tmp/real_320k.flac",
            cutoff_hz=21000.0,
            r2_url="https://r2.drops.audio/real_320k.flac",
        )
        self.assertEqual(upgraded.status, QueueStatus.VERIFIED_HQ)
        self.assertEqual(len(self.queue_mgr.get_pending_hunts()), 0)

    def test_engine_policies(self):
        engine_downsize = DropSoulEngine(default_policy="auto_downsize")
        self.assertEqual(
            engine_downsize.prompt_user_decision(1, "Artist", "Title"),
            DecisionAction.DOWNSIZE
        )

        engine_wait = DropSoulEngine(default_policy="auto_wait")
        self.assertEqual(
            engine_wait.prompt_user_decision(1, "Artist", "Title"),
            DecisionAction.WAIT
        )

        engine_skip = DropSoulEngine(default_policy="auto_skip")
        self.assertEqual(
            engine_skip.prompt_user_decision(1, "Artist", "Title"),
            DecisionAction.SKIP
        )


if __name__ == "__main__":
    unittest.main()
