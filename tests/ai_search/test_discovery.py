import unittest
from ai_search.discovery import MovieCandidate, _parse_json_candidates, looks_like_discovery_query


class DiscoveryTests(unittest.TestCase):
    def test_person_movie_query_is_discovery(self):
        self.assertTrue(looks_like_discovery_query("Duniya Vijay movies"))

    def test_long_natural_language_query_is_discovery(self):
        self.assertTrue(looks_like_discovery_query(
            "Find Kannada movies where the hero and heroine acted together after 2015 "
            "and include the release year and only real movie titles in the answer."
        ))

    def test_file_query_stays_legacy(self):
        self.assertFalse(looks_like_discovery_query("Yajamana 2019 720p"))

    def test_json_candidate_parser(self):
        results = _parse_json_candidates(
            '{"movies":[{"title":"Salaga","year":2021},{"title":"Duniya","year":2007}]}'
        )
        self.assertEqual([(x.title, x.year) for x in results], [("Salaga", 2021), ("Duniya", 2007)])


if __name__ == "__main__":
    unittest.main()
