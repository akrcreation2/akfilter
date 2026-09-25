import unittest
from ai_search.grouping import group_results
from ai_search.models import SearchResult

class GroupingTests(unittest.TestCase):
    def test_numeric_series_order(self):
        results = [SearchResult(str(i), "Show", season=1, episode=i) for i in (10, 2, 1)]
        group = group_results(results)[0]
        self.assertEqual(list(group.seasons[1]), [1, 2, 10])

    def test_movie_group(self):
        self.assertEqual(len(group_results([SearchResult("1", "Movie"), SearchResult("2", "Movie")])), 1)

if __name__ == "__main__": unittest.main()
