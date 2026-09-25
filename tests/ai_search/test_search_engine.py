import unittest
from ai_search.entities import SearchProvider
from ai_search.models import SearchResult
from ai_search.parser import QueryParser
from ai_search.search_engine import SearchEngine

class Provider(SearchProvider):
    async def search(self, intent): return [SearchResult("1", "Darshan", size_bytes=400*1024**2)]

class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_failure_is_safe(self):
        class Broken(SearchProvider):
            async def search(self, intent): raise RuntimeError("offline")
        result = await SearchEngine(Broken()).search(QueryParser().parse("Darshan movie"))
        self.assertEqual(result, [])
    async def test_search(self):
        result = await SearchEngine(Provider()).search(QueryParser().parse("Darshan movie"))
        self.assertEqual(result[0].file_id, "1")

if __name__ == "__main__": unittest.main()
