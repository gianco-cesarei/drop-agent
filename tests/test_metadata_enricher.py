"""
Unit tests for Milestone 3: Discogs & Beatport Enrichment, Artwork Manager, and ID3v2.4 Tagging.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrichment.discogs_client import DiscogsClient
from enrichment.beatport_client import BeatportClient
from enrichment.artwork_manager import ArtworkManager
from enrichment.metadata_tagger import MetadataTagger
from enrichment.metadata_enricher import MetadataEnricher, EnrichedTrackMetadata


class TestDiscogsClient(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.client = DiscogsClient(token="test_token", cache_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_client_initialization(self):
        self.assertTrue(self.client.is_authenticated)
        self.assertEqual(self.client.token, "test_token")

    def test_parse_search_result(self):
        raw_item = {
            "id": 123456,
            "title": "Adrien Calvet - Summer of 05",
            "label": ["Sahko Recordings"],
            "catno": "SAHKO01",
            "year": "2020",
            "country": "France",
            "style": ["Deep House", "Minimal"],
            "genre": ["Electronic"],
            "cover_image": "https://img.discogs.com/test.jpg",
            "uri": "/release/123456-adrien-calvet"
        }
        res = self.client._parse_search_result(raw_item)
        self.assertEqual(res["label"], "Sahko Recordings")
        self.assertEqual(res["catalog_number"], "SAHKO01")
        self.assertEqual(res["release_year"], "2020")
        self.assertEqual(res["styles"], ["Deep House", "Minimal"])
        self.assertEqual(res["discogs_url"], "https://www.discogs.com/release/123456-adrien-calvet")


class TestBeatportClient(unittest.TestCase):
    def setUp(self):
        self.client = BeatportClient()

    def test_parse_api_track(self):
        item = {
            "id": 98765,
            "name": "Summer of 05",
            "artists": [{"name": "Adrien Calvet"}],
            "release": {
                "label": {"name": "Sahko Recordings"},
                "catalog_number": "SAHKO01",
                "publish_date": "2020-05-10",
                "image": {"dynamic_uri": "https://geo-media.beatport.com/image_size/{w}x{h}/test.jpg"}
            },
            "bpm": 124.0,
            "key": {"name": "A min"},
            "genre": {"name": "Deep House"},
            "slug": "summer-of-05"
        }
        parsed = self.client._parse_api_track(item)
        self.assertEqual(parsed["artist"], "Adrien Calvet")
        self.assertEqual(parsed["label"], "Sahko Recordings")
        self.assertEqual(parsed["bpm"], 124.0)
        self.assertEqual(parsed["key"], "A min")
        self.assertEqual(parsed["artwork_url"], "https://geo-media.beatport.com/image_size/1400x1400/test.jpg")
        self.assertIn("beatport.com/track/summer-of-05/98765", parsed["buy_url"])


class TestArtworkManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ArtworkManager(target_size=1400)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_process_image_bytes(self):
        # Create a small 200x300 image in memory
        orig = Image.new("RGB", (200, 300), color=(100, 150, 200))
        buf = io.BytesIO()
        orig.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        out_path = os.path.join(self.temp_dir, "processed_1400.jpg")
        result = self.manager.process_image_bytes(raw_bytes, out_path, size=1400)
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(out_path))

        # Check saved image dimensions
        with Image.open(out_path) as img:
            self.assertEqual(img.size, (1400, 1400))
            self.assertEqual(img.mode, "RGB")

    def test_generate_fallback_artwork(self):
        out_path = os.path.join(self.temp_dir, "fallback_cover.jpg")
        result = self.manager.generate_fallback_artwork(
            title="Summer of 05",
            artist="Adrien Calvet",
            label="Sahko",
            genre="Deep House",
            output_path=out_path,
            size=1400
        )
        self.assertTrue(os.path.exists(result))
        with Image.open(result) as img:
            self.assertEqual(img.size, (1400, 1400))


class TestMetadataEnricher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.enricher = MetadataEnricher(cache_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.object(DiscogsClient, "search_release")
    @patch.object(BeatportClient, "search_track")
    def test_enrich_track(self, mock_beatport, mock_discogs):
        mock_discogs.return_value = {
            "label": "Warp Records",
            "catalog_number": "WARP001",
            "release_year": "1998",
            "country": "UK",
            "styles": ["IDM", "Deep House"],
            "genres": ["Electronic"],
            "cover_image_url": "https://img.discogs.com/test.jpg",
            "discogs_url": "https://www.discogs.com/release/warp001"
        }
        mock_beatport.return_value = {
            "buy_url": "https://www.beatport.com/track/test/1",
            "bpm": 126.0,
            "key": "A Minor"
        }

        meta = self.enricher.enrich_track(
            artist="Boards of Canada",
            title="Roygbiv",
            bpm=None,
            camelot_key="8A"
        )
        self.assertEqual(meta.artist, "Boards of Canada")
        self.assertEqual(meta.record_label, "Warp Records")
        self.assertEqual(meta.catalog_number, "WARP001")
        self.assertEqual(meta.original_year, "1998")
        self.assertEqual(meta.bpm, 126.0)
        self.assertEqual(meta.camelot_key, "8A")
        self.assertIn("discogs", meta.buy_links)
        self.assertIn("beatport", meta.buy_links)


if __name__ == "__main__":
    unittest.main()
