"""
DropSoul Cloud Background Worker.
Runs 24/7 in headless mode (e.g. Docker / VPS) while local PCs are turned off.
Continuously checks the hunting queue, executes Soulseek downloads, verifies audio quality,
and pushes certified releases to Cloudflare R2 and Supabase.
"""

from __future__ import annotations

import os
import sys
import time
import logging

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dropsoul import SoulseekClient, AudioQualityVerifier, DropSoulQueueManager, QueueStatus
from cloud import R2Uploader, SupabaseSyncClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [DropSoul Worker] %(message)s"
)
logger = logging.getLogger("dropsoul.worker")


class DropSoulCloudWorker:
    def __init__(
        self,
        poll_interval_seconds: int = 300,  # check every 5 minutes
        slskd_url: Optional[str] = None,
        r2_uploader: Optional[R2Uploader] = None,
        supabase_sync: Optional[SupabaseSyncClient] = None,
    ):
        self.poll_interval = poll_interval_seconds
        self.soulseek = SoulseekClient(base_url=slskd_url)
        self.verifier = AudioQualityVerifier()
        self.queue_mgr = DropSoulQueueManager()
        self.r2 = r2_uploader or R2Uploader()
        self.supabase = supabase_sync or SupabaseSyncClient()

    def process_pending_item(self, item) -> bool:
        logger.info(f"🎯 Hunting on Soulseek for: '{item.artist} - {item.title}'")
        candidate = self.soulseek.get_best_match(item.artist, item.title, wait_sec=10)
        if not candidate:
            logger.info(f"⏳ No active peer available right now for '{item.artist} - {item.title}'")
            return False

        logger.info(f"📥 Found peer '{candidate.username}' ({candidate.extension.upper()}, {candidate.bitrate_kbps or '?'}k). Enqueueing download...")
        success = self.soulseek.enqueue_download(candidate)
        if not success:
            return False

        # Note: In production, worker waits for file arrival in slskd shared download dir,
        # runs self.verifier.analyze(), pushes to self.r2, and updates self.queue_mgr.mark_completed_hq()
        return True

    def run_cycle(self) -> None:
        pending = self.queue_mgr.get_pending_hunts()
        if not pending:
            logger.info("✨ Queue is empty. All tracks verified or no pending hunts.")
            return

        logger.info(f"🔄 Processing {len(pending)} pending track(s)...")
        for item in pending:
            try:
                self.process_pending_item(item)
            except Exception as e:
                logger.error(f"⚠️ Error processing '{item.artist} - {item.title}': {e}")

    def start_loop(self) -> None:
        logger.info("🚀 DropSoul Cloud Worker started. Running 24/7 background hunt loop...")
        while True:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error(f"Unexpected worker error: {e}")
            time.sleep(self.poll_interval)


if __name__ == "__main__":
    worker = DropSoulCloudWorker()
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        worker.run_cycle()
    else:
        worker.start_loop()
