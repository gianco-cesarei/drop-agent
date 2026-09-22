"""
DropSoul — High-Fidelity Audio Ingestion & Spectral Verification Engine for Drops.
"""

from .quality_verifier import AudioQualityVerifier, QualityVerdict, QualityReport
from .soulseek_client import SoulseekClient, SoulseekSearchResult, SoulseekDownloadStatus
from .queue_manager import DropSoulQueueManager, QueueTrackItem, QueueStatus
from .engine import DropSoulEngine, DecisionAction

__all__ = [
    "AudioQualityVerifier",
    "QualityVerdict",
    "QualityReport",
    "SoulseekClient",
    "SoulseekSearchResult",
    "SoulseekDownloadStatus",
    "DropSoulQueueManager",
    "QueueTrackItem",
    "QueueStatus",
    "DropSoulEngine",
    "DecisionAction",
]
