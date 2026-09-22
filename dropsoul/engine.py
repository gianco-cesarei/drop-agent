"""
DropSoul Engine — Core orchestrator for Soulseek P2P, Spectrogram Quality Verification,
and Decision Gate (Downsizing vs Aspetta/Hunt vs Salta).
"""

from __future__ import annotations

import os
import sys
import logging
from enum import Enum
from typing import Optional, Callable

from .quality_verifier import AudioQualityVerifier, QualityVerdict, QualityReport
from .soulseek_client import SoulseekClient, SoulseekSearchResult
from .queue_manager import DropSoulQueueManager, QueueStatus

logger = logging.getLogger("dropsoul.engine")


class DecisionAction(str, Enum):
    DOWNSIZE = "DOWNSIZE"  # Download low-res WebRip + queue background hunt
    WAIT = "WAIT"          # No low-res audio; place in queue for pure HQ
    SKIP = "SKIP"          # Exclude track entirely


class DropSoulEngine:
    def __init__(
        self,
        soulseek_client: Optional[SoulseekClient] = None,
        quality_verifier: Optional[AudioQualityVerifier] = None,
        queue_manager: Optional[DropSoulQueueManager] = None,
        default_policy: str = "interactive",  # "interactive", "auto_downsize", "auto_wait", "auto_skip"
    ):
        self.soulseek = soulseek_client or SoulseekClient()
        self.verifier = quality_verifier or AudioQualityVerifier()
        self.queue = queue_manager or DropSoulQueueManager()
        self.default_policy = default_policy

    def prompt_user_decision(
        self,
        track_num: int,
        artist: str,
        title: str,
        reason: str = "HQ release not immediately available",
    ) -> DecisionAction:
        """
        Interactive Decision Gate for the curator.
        Returns DOWNSIZE, WAIT, or SKIP.
        """
        if self.default_policy == "auto_downsize":
            return DecisionAction.DOWNSIZE
        elif self.default_policy == "auto_wait":
            return DecisionAction.WAIT
        elif self.default_policy == "auto_skip":
            return DecisionAction.SKIP

        print("\n" + "=" * 65)
        print(f"🎛️  [DropSoul Decision Gate] Traccia {track_num:02d}: '{artist} - {title}'")
        print(f"    Causa: {reason}")
        print("=" * 65)
        print("Scegli come procedere per questa release:")
        print("  [1] ⚡ Downsizing: Scarica WebRip provvisorio + metti in coda DropSoul nel cloud")
        print("  [2] ⏳ Aspetta:    Rifiuta bassa risoluzione; tieni lo slot in attesa per vero 320k/FLAC")
        print("  [3] ⏭️  Salta:      Escludi la traccia dal set")
        print("-" * 65)

        while True:
            try:
                choice = input("Digita opzione [1, 2, 3] (default 1): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[DropSoul] Defaulting to Downsizing.")
                return DecisionAction.DOWNSIZE

            if choice in ["1", "", "d", "downsize"]:
                return DecisionAction.DOWNSIZE
            elif choice in ["2", "w", "wait", "aspetta"]:
                return DecisionAction.WAIT
            elif choice in ["3", "s", "skip", "salta"]:
                return DecisionAction.SKIP
            else:
                print("⚠️ Scelta non valida. Digita 1 (Downsizing), 2 (Aspetta) o 3 (Salta).")

    def process_track(
        self,
        track_num: int,
        artist: str,
        title: str,
        album_title: str,
        youtube_fallback_fn: Optional[Callable[[], Optional[str]]] = None,
    ) -> Optional[str]:
        """
        Main acquisition logic for DropSoul:
        1. Search Soulseek for high-bitrate candidate (FLAC / 320k).
        2. If candidate found and downloaded, run Spectrogram Verification (>20kHz).
        3. If verified genuine -> return file path.
        4. If not available or fake transcode -> invoke Decision Gate:
           - DOWNSIZE: Call fallback, save placeholder, queue background hunt.
           - WAIT: Queue background hunt, return None (slot reserved).
           - SKIP: Ignore track, return None.
        """
        print(f"\n[DropSoul] 🔍 Searching Soulseek for HQ release: '{artist} - {title}'...")
        candidate = self.soulseek.get_best_match(artist, title)

        downloaded_hq_path: Optional[str] = None
        if candidate:
            print(
                f"[DropSoul] 🎯 Found peer '{candidate.username}' | "
                f"Format: {candidate.extension.upper()} | Bitrate: {candidate.bitrate_kbps or '?'}k | Queue: {candidate.queue_length}"
            )
            # In a real environment, download via slskd
            # If slskd is offline or simulation, downloaded_hq_path stays None

        # If we have a candidate downloaded, verify spectrum
        if downloaded_hq_path and os.path.exists(downloaded_hq_path):
            report = self.verifier.analyze(downloaded_hq_path)
            print(f"[DropSoul] 🔬 Spectral Analysis: {report.summary()}")
            if report.is_genuine:
                print(f"[DropSoul] ✅ Quality Verified ({report.cutoff_frequency_hz:.0f} Hz >= 20kHz). Studio Grade.")
                return downloaded_hq_path
            else:
                print(f"[DropSoul] ⚠️ Rejected: Fake transcode detected! ({report.details})")
                try:
                    os.remove(downloaded_hq_path)
                except OSError:
                    pass

        # If not acquired or rejected, trigger Decision Gate
        decision = self.prompt_user_decision(
            track_num=track_num,
            artist=artist,
            title=title,
            reason="Nessuna sorgente HQ verificata (>20kHz) disponibile istantaneamente su Soulseek",
        )

        if decision == DecisionAction.DOWNSIZE:
            print(f"[DropSoul] ⚡ Downsizing approvato: download WebRip provvisorio...")
            downsized_path = youtube_fallback_fn() if youtube_fallback_fn else None
            self.queue.add_track(
                artist=artist,
                title=title,
                album_title=album_title,
                status=QueueStatus.DOWNSIZED_PLACEHOLDER,
                downsized_file_path=downsized_path,
            )
            return downsized_path

        elif decision == DecisionAction.WAIT:
            print(f"[DropSoul] ⏳ Pure Quality: slot riservato. Traccia accodata in DropSoul per vero 320k/FLAC.")
            self.queue.add_track(
                artist=artist,
                title=title,
                album_title=album_title,
                status=QueueStatus.PENDING_HUNT,
            )
            return None

        elif decision == DecisionAction.SKIP:
            print(f"[DropSoul] ⏭️ Traccia esclusa dalla selezione.")
            return None

        return None
