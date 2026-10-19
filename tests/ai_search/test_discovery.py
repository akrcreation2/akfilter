import unittest
from ai_search.discovery import (MovieCandidate, _parse_json_candidates, looks_like_discovery_query, _person_hint_from_natural_query, _person_query_role)


class DiscoveryTests(unittest.TestCase):
    def test_person_movie_query_is_discovery(self):
        self.assertTrue(looks_like_discovery_query("Duniya Vijay movies"))

    def test_plain_person_query_uses_database_first(self):
        self.assertFalse(looks_like_discovery_query("Duniya Vijay"))

    def test_movie_title_query_uses_database_first(self):
        self.assertFalse(looks_like_discovery_query("Yajamana"))

    def test_title_and_language_uses_database_first(self):
        self.assertFalse(looks_like_discovery_query("Kantara Kannada"))

    def test_language_only_uses_database_first(self):
        self.assertFalse(looks_like_discovery_query("Kannada"))

    def test_long_natural_language_query_is_discovery(self):
        self.assertTrue(looks_like_discovery_query(
            "Find Kannada movies where the hero and heroine acted together after 2015 "
            "and include the release year and only real movie titles in the answer."
        ))

    def test_file_query_stays_legacy(self):
        self.assertFalse(looks_like_discovery_query("Yajamana 2019 720p"))


    def test_natural_actor_question_extracts_name(self):
        self.assertEqual(_person_hint_from_natural_query("Yash acted in which movies"), "yash")

    def test_director_query_extracts_name(self):
        self.assertEqual(_person_hint_from_natural_query("Rishab Shetty direction movies"), "rishab shetty")
        self.assertEqual(_person_query_role("Rishab Shetty direction movies"), "director")

    def test_actor_query_defaults_to_cast(self):
        self.assertEqual(_person_query_role("Yash movies"), "cast")

    def test_natural_actor_question_extracts_name(self):
        self.assertEqual(_person_hint_from_natural_query("Yash acted in which movies"), "Yash")

    def test_director_query_extracts_name(self):
        self.assertEqual(_person_hint_from_natural_query("Rishab Shetty direction movies"), "Rishab Shetty")
        self.assertEqual(_person_query_role("Rishab Shetty direction movies"), "director")

    def test_actor_query_defaults_to_cast(self):
        self.assertEqual(_person_query_role("Yash movies"), "cast")

    def test_json_candidate_parser(self):
        results = _parse_json_candidates(
            '{"movies":[{"title":"Salaga","year":2021},{"title":"Duniya","year":2007}]}'
        )
        self.assertEqual([(x.title, x.year) for x in results], [("Salaga", 2021), ("Duniya", 2007)])


if __name__ == "__main__":
    unittest.main()


def test_tmdb_language_codes_cover_indian_languages():
    from ai_search.discovery import _TMDB_LANGUAGE_CODES
    assert _TMDB_LANGUAGE_CODES["kannada"] == "kn"
    assert _TMDB_LANGUAGE_CODES["tamil"] == "ta"
    assert _TMDB_LANGUAGE_CODES["telugu"] == "te"
    assert _TMDB_LANGUAGE_CODES["malayalam"] == "ml"
    assert _TMDB_LANGUAGE_CODES["hindi"] == "hi"


def test_tmdb_disabled_without_credentials(monkeypatch):
    from ai_search.discovery import _tmdb_enabled
    monkeypatch.delenv("TMDB_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    assert _tmdb_enabled() is False
