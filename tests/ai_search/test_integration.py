import unittest
import asyncio
from ai_search import QueryParser
from ai_search.models import SearchResult
from ai_search.ranking import rank_results
from ai_search.grouping import group_results
from ai_search.sorting import sort_results


class IntegrationTests(unittest.TestCase):
    """Test AI search integration with realistic movie/series queries."""
    
    def setUp(self):
        self.parser = QueryParser()
    
    def test_parser_realistic_kannada_query(self):
        """Test: 'ದರ್ಶನ್ ಕನ್ನಡ ಚಿತ್ರ'"""
        intent = self.parser.parse("ದರ್ಶನ್ ಕನ್ನಡ ಚಿತ್ರ")
        self.assertEqual(intent.person, "Darshan")
        self.assertEqual(intent.language, "Kannada")
        self.assertEqual(intent.content_type, "movie")
        self.assertGreater(intent.confidence, 0.5)
    
    def test_parser_kannada_with_size_quality(self):
        """Test: 'ದರ್ಶನ್ ಕನ್ನಡ ಚಿತ್ರ 400MB 1080p'"""
        intent = self.parser.parse("ದರ್ಶನ್ ಕನ್ನಡ ಚಿತ್ರ 400MB 1080p")
        self.assertEqual(intent.person, "Darshan")
        self.assertEqual(intent.language, "Kannada")
        self.assertEqual(intent.content_type, "movie")
        self.assertEqual(intent.target_size_mb, 400)
        self.assertEqual(intent.quality, "1080p")
    
    def test_parser_english_with_year(self):
        """Test: 'Darshan Kannada movie 1080p'"""
        intent = self.parser.parse("Darshan Kannada movie 1080p")
        self.assertEqual(intent.person, "Darshan")
        self.assertEqual(intent.language, "Kannada")
        self.assertEqual(intent.content_type, "movie")
        self.assertEqual(intent.quality, "1080p")
    
    def test_parser_title_vs_person_kantara(self):
        """Test: 'Kantara Kannada 2022 700MB' (title, not person)"""
        intent = self.parser.parse("Kantara Kannada 2022 700MB")
        self.assertEqual(intent.title, "Kantara")
        self.assertIsNone(intent.person)  # Kantara is not Darshan
        self.assertEqual(intent.language, "Kannada")
        self.assertEqual(intent.year, 2022)
        self.assertEqual(intent.target_size_mb, 700)
    
    def test_parser_kgf_hindi_4k(self):
        """Test: 'KGF Chapter 2 Hindi 2GB 4K'"""
        intent = self.parser.parse("KGF Chapter 2 Hindi 2GB 4K")
        self.assertEqual(intent.title, "KGF")
        self.assertEqual(intent.language, "Hindi")
        self.assertEqual(intent.target_size_mb, 2048)
        self.assertEqual(intent.quality, "2160p")
    
    def test_ranking_by_size_proximity(self):
        """Test that ranking prioritizes files near target size."""
        intent = self.parser.parse("Darshan movie 400MB")
        results = [
            SearchResult("1", "Darshan Movie", size_bytes=390*1024**2),  # 390 MB
            SearchResult("2", "Darshan Movie", size_bytes=405*1024**2),  # 405 MB
            SearchResult("3", "Darshan Movie", size_bytes=900*1024**2),  # 900 MB
        ]
        ranked = rank_results(results, intent)
        # 390MB and 405MB should score higher than 900MB
        self.assertIn(ranked[0].file_id, {"1", "2"})
        self.assertEqual(ranked[-1].file_id, "3")
    
    def test_ranking_by_quality_match(self):
        """Test that ranking prioritizes requested quality."""
        intent = self.parser.parse("Darshan movie 1080p")
        results = [
            SearchResult("1", "Darshan Movie", quality="1080p"),
            SearchResult("2", "Darshan Movie", quality="720p"),
            SearchResult("3", "Darshan Movie", quality="480p"),
        ]
        ranked = rank_results(results, intent)
        self.assertEqual(ranked[0].file_id, "1")  # 1080p ranked first
    
    def test_grouping_movies(self):
        """Test that movies are grouped by title."""
        results = [
            SearchResult("1", "Darshan Movie 2024", size_bytes=400*1024**2),
            SearchResult("2", "Darshan Movie 2024", size_bytes=700*1024**2),
        ]
        grouped = group_results(results)
        self.assertEqual(len(grouped), 1)  # Single group
        self.assertEqual(len(grouped[0].files), 2)
    
    def test_grouping_series(self):
        """Test that series episodes are grouped by season/episode."""
        results = [
            SearchResult("1", "Series", season=1, episode=1),
            SearchResult("2", "Series", season=1, episode=2),
            SearchResult("3", "Series", season=2, episode=1),
        ]
        grouped = group_results(results)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[0].seasons[1]), 2)  # S01: 2 episodes
        self.assertEqual(len(grouped[0].seasons[2]), 1)  # S02: 1 episode
    
    def test_sorting_ascending_size(self):
        """Test sorting small to large."""
        results = [
            SearchResult("1", "Movie", size_bytes=900*1024**2),
            SearchResult("2", "Movie", size_bytes=100*1024**2),
            SearchResult("3", "Movie", size_bytes=500*1024**2),
        ]
        sorted_results = sort_results(results, "smallest")
        self.assertEqual(sorted_results[0].file_id, "2")  # 100MB first
        self.assertEqual(sorted_results[1].file_id, "3")  # 500MB second
        self.assertEqual(sorted_results[2].file_id, "1")  # 900MB last
    
    def test_sorting_descending_size(self):
        """Test sorting large to small."""
        results = [
            SearchResult("1", "Movie", size_bytes=100*1024**2),
            SearchResult("2", "Movie", size_bytes=900*1024**2),
            SearchResult("3", "Movie", size_bytes=500*1024**2),
        ]
        sorted_results = sort_results(results, "largest")
        self.assertEqual(sorted_results[0].file_id, "2")  # 900MB first
        self.assertEqual(sorted_results[1].file_id, "3")  # 500MB second
        self.assertEqual(sorted_results[2].file_id, "1")  # 100MB last
    
    def test_sorting_random_deterministic(self):
        """Test that random sorting is deterministic with same seed."""
        results = [SearchResult(str(i), f"Movie {i}", size_bytes=i*1024**2) for i in range(10)]
        sorted1 = sort_results(results, "random", seed=42)
        sorted2 = sort_results(results, "random", seed=42)
        self.assertEqual([r.file_id for r in sorted1], [r.file_id for r in sorted2])
    
    def test_fallback_on_low_confidence(self):
        """Test that parser marks low-confidence queries appropriately."""
        intent = self.parser.parse("â² â²")
        # Gibberish should have low confidence
        self.assertLess(intent.confidence, 0.8)


if __name__ == "__main__":
    unittest.main()
