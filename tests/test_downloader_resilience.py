import unittest
from downloader import _clean_text

class TestDownloaderResilience(unittest.TestCase):
    def test_clean_text(self):
        raw = "01. Artist - Track Name (Official Video) [HQ]"
        cleaned = _clean_text(raw)
        self.assertEqual(cleaned, "Artist - Track Name")

    def test_clean_text_noise(self):
        raw = "Track Title [Premiere] (Official Audio)"
        cleaned = _clean_text(raw)
        self.assertEqual(cleaned, "Track Title")

if __name__ == "__main__":
    unittest.main()
