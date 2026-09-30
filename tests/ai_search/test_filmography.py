import unittest
from ai_search.filmography import match_person_title, titles_for_person
from ai_search import QueryParser


class FilmographyTests(unittest.TestCase):
    def test_darshan_has_known_titles(self):
        titles = {title for title, _ in titles_for_person("Darshan")}
        self.assertIn("Yajamana", titles)
        self.assertIn("Kaatera", titles)
        self.assertIn("Krantiveera Sangolli Rayanna", titles)

    def test_match_from_filename(self):
        title, year = match_person_title("Yajamana 2019 Kannada 720p HDRip.mkv", "Darshan")
        self.assertEqual(title, "Yajamana")
        self.assertEqual(year, 2019)

    def test_person_query_uses_year_order(self):
        intent = QueryParser().parse("Darshan movies")
        self.assertEqual(intent.person, "Darshan")
        self.assertEqual(intent.sort_order, "year")


if __name__ == "__main__":
    unittest.main()

class _FakeCursor:
    def __init__(self, files):
        self.files = files

    async def to_list(self, length=None):
        return self.files[:length] if length else list(self.files)


class _FakeMedia:
    last_filter = None
    files = []

    @classmethod
    def find(cls, query_filter):
        cls.last_filter = query_filter
        return _FakeCursor(cls.files)


class ProviderFilmographyTests(unittest.IsolatedAsyncioTestCase):
    async def test_person_search_expands_to_existing_titles(self):
        import sys
        import types
        from types import SimpleNamespace
        from ai_search import QueryParser
        from ai_search.adapter import MongoDBSearchProvider
        from ai_search.search_engine import SearchEngine

        fake_db = types.ModuleType("database.ia_filterdb")
        fake_db.Media = _FakeMedia
        old = sys.modules.get("database.ia_filterdb")
        sys.modules["database.ia_filterdb"] = fake_db
        try:
            _FakeMedia.files = [
                SimpleNamespace(file_id="1", file_name="Yajamana 2019 Kannada 720p.mkv", file_size=1000, file_type="document", mime_type="video/x-matroska", caption=None),
                SimpleNamespace(file_id="2", file_name="Kaatera 2023 Kannada 1080p.mkv", file_size=2000, file_type="document", mime_type="video/x-matroska", caption=None),
                SimpleNamespace(file_id="3", file_name="Random Movie 2023 Kannada 1080p.mkv", file_size=3000, file_type="document", mime_type="video/x-matroska", caption=None),
            ]
            intent = QueryParser().parse("Darshan Kannada movies")
            results = await SearchEngine(MongoDBSearchProvider()).search(intent)
            names = [r.title for r in results]
            self.assertEqual(names, [
                "Kaatera 2023 Kannada 1080p.mkv",
                "Yajamana 2019 Kannada 720p.mkv",
            ])
            self.assertEqual(results[0].year, 2023)
            self.assertEqual(results[0].metadata["matched_person"], "Darshan")
            # Person filmographies are queried in bounded chunks, so the fake
            # provider sees the last chunk rather than one giant regex.
            self.assertIn("Kaatera", _FakeMedia.last_filter["$or"][0]["file_name"].pattern)
        finally:
            if old is None:
                sys.modules.pop("database.ia_filterdb", None)
            else:
                sys.modules["database.ia_filterdb"] = old
