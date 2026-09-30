import unittest
from ai_search.parser import QueryParser

class ParserTests(unittest.TestCase):
    def setUp(self): self.parser = QueryParser()
    def test_realistic_queries(self):
        cases = [
            ("Darshan Kannada movie", "Darshan", "Kannada", "movie"),
            ("ದರ್ಶನ್ ಕನ್ನಡ ಚಿತ್ರ 400MB 1080p", "Darshan", "Kannada", "movie"),
            ("Kantara Kannada 720p", None, "Kannada", "Kantara"),
            ("KGF 2 1GB", None, None, "KGF"),
        ]
        for query, person, language, title in cases:
            intent = self.parser.parse(query)
            self.assertEqual(intent.person, person)
            self.assertEqual(intent.language, language)
            if title == "movie": self.assertEqual(intent.content_type, title)
            else: self.assertEqual(intent.title, title)
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

    def test_long_natural_language_person_query(self):
        query = (
            "Please find all movies acted by Yash and Radhika Pandit in Kannada, "
            "prefer the latest available releases and show only files that are "
            "actually present in the database."
        )
        intent = self.parser.parse(query)
        self.assertIn("Yash", intent.persons)
        self.assertIn("Radhika Pandit", intent.persons)
        self.assertEqual(intent.language, "Kannada")
        self.assertEqual(intent.content_type, "movie")

    def test_relative_current_year(self):
        from datetime import datetime, timezone
        intent = self.parser.parse("this year Kannada movies")
        self.assertEqual(intent.year, datetime.now(timezone.utc).year)

if __name__ == "__main__": unittest.main()
