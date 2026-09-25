import unittest
from ai_search.parser import QueryParser

class ParserTests(unittest.TestCase):
    def setUp(self): self.parser = QueryParser()
    def test_multilingual_actor(self):
        for query in ["Darshan Kannada movie", "ದರ್ಶನ್ ಕನ್ನಡ ಚಿತ್ರ", "Darshan avara Kannada movies"]:
            intent = self.parser.parse(query)
            self.assertEqual(intent.person, "Darshan"); self.assertEqual(intent.language, "Kannada"); self.assertEqual(intent.content_type, "movie")
    def test_typo_and_filters(self):
        intent = self.parser.parse("darshn kannda movi 2015 400MB 1080p")
        self.assertEqual(intent.person, "Darshan"); self.assertEqual(intent.language, "Kannada")
        self.assertEqual(intent.year, 2015); self.assertEqual(intent.target_size_mb, 400); self.assertEqual(intent.quality, "1080p")
        self.assertTrue(intent.corrections)
    def test_series_markers(self):
        self.assertEqual(self.parser.parse("Series S02").season, 2)
        self.assertEqual(self.parser.parse("Series episode 5").episode, 5)
    def test_title_disambiguation(self):
        intent = self.parser.parse("Kantara Kannada")
        self.assertEqual(intent.title, "Kantara"); self.assertIsNone(intent.person)

if __name__ == "__main__": unittest.main()
