import unittest
from ai_search.models import SearchIntent, SearchResult
from ai_search.ranking import rank_results
from ai_search.sorting import sort_results

class RankingSortingTests(unittest.TestCase):
    def setUp(self):
        self.intent = SearchIntent("Darshan 400MB", title="Darshan", person="Darshan", target_size_mb=400)
        self.items = [SearchResult(str(i), "Darshan", size_bytes=s*1024**2) for i, s in enumerate((398, 402, 900))]
    def test_size_proximity(self):
        ranked = rank_results(self.items, self.intent)
        self.assertEqual(ranked[0].size_bytes // 1024**2, 398)
    def test_sorting(self):
        self.assertEqual([x.size_bytes for x in sort_results(self.items, "smallest")], sorted(x.size_bytes for x in self.items))
        self.assertEqual([x.size_bytes for x in sort_results(self.items, "largest")], sorted((x.size_bytes for x in self.items), reverse=True))
    def test_deterministic_random(self):
        self.assertEqual([x.file_id for x in sort_results(self.items, "random", seed=4)], [x.file_id for x in sort_results(self.items, "random", seed=4)])

if __name__ == "__main__": unittest.main()
