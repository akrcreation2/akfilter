import unittest
from ai_search.metadata import normalize_media_metadata
from ai_search.normalization import normalize_language

class MetadataTests(unittest.TestCase):
    def test_resolution(self):
        data = normalize_media_metadata({"width": 1920, "height": 1080})
        self.assertEqual(data["quality"], "1080p"); self.assertEqual(data["resolution"], (1920, 1080))
    def test_language(self): self.assertEqual(normalize_language("ಕನ್ನಡದ"), "Kannada")

if __name__ == "__main__": unittest.main()
