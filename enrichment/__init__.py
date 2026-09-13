"""
Enrichment package for Drop Agent: Discogs, Beatport, Artwork, ID3v2.4 Tagging.
"""

from .discogs_client import DiscogsClient
from .beatport_client import BeatportClient
from .artwork_manager import ArtworkManager
from .metadata_tagger import MetadataTagger
from .metadata_enricher import MetadataEnricher, EnrichedTrackMetadata

__all__ = [
    "DiscogsClient",
    "BeatportClient",
    "ArtworkManager",
    "MetadataTagger",
    "MetadataEnricher",
    "EnrichedTrackMetadata",
]
