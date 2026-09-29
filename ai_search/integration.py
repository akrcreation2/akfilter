"""Integration of AI search into existing Telegram bot flow.

Provides a high-level interface for the bot to use AI-powered search while
maintaining seamless fallback to existing regex-based search.
"""
import logging
from typing import List, Optional, Tuple
from ai_search import QueryParser, SearchEngine
from ai_search.adapter import MongoDBSearchProvider
from ai_search.grouping import group_results
from ai_search.sorting import sort_results
from ai_search.models import SearchResult, GroupedResult
from database.ia_filterdb import get_search_results as legacy_search_results

logger = logging.getLogger(__name__)


class AISearchIntegration:
    """Bridges AI search engine to existing bot search flow.
    
    Attempts AI-powered search first, falls back to existing regex search.
    Handles ranking, grouping, and sorting intelligently.
    """
    
    def __init__(self):
        self.parser = QueryParser()
        self.provider = MongoDBSearchProvider()
        self.engine = SearchEngine(self.provider)
        self.min_confidence = 0.3  # Fallback if confidence below this
    
    async def search(self, query: str, file_type: Optional[str] = None, 
                     max_results: int = 10, offset: int = 0) -> Tuple[List, Optional[int], int]:
        """Search using AI intent parsing and ranking, with fallback.
        
        Args:
            query: User's natural-language search query
            file_type: Optional file type filter
            max_results: Max results to return
            offset: Pagination offset
        
        Returns:
            (results, next_offset, total_count) - compatible with legacy search API
        """
        try:
            # Parse query intent
            intent = self.parser.parse(query)
            logger.debug(f"Parsed intent: person={intent.person}, title={intent.title}, "
                        f"language={intent.language}, confidence={intent.confidence}")
            
            # If confidence is high, try AI-powered search
            if intent.confidence >= self.min_confidence:
                try:
                    ai_results = await self.engine.search(intent, limit=max_results + offset)
                    
                    # If we got good results, use them
                    if ai_results and len(ai_results) > 0:
                        logger.debug(f"AI search returned {len(ai_results)} results")
                        
                        # Group results (movie vs series)
                        grouped = group_results(ai_results)
                        
                        # Flatten grouped results for pagination
                        flat_results = []
                        for group in grouped:
                            if group.seasons:
                                # Series: flatten episodes in order
                                for season_num in sorted(group.seasons.keys()):
                                    for episode_num in sorted(group.seasons[season_num].keys()):
                                        flat_results.extend(group.seasons[season_num][episode_num])
                            else:
                                # Movie: just add files
                                flat_results.extend(group.files)
                        
                        # Apply pagination
                        total = len(flat_results)
                        next_offset = offset + max_results if offset + max_results < total else ''
                        paginated = flat_results[offset:offset + max_results]
                        
                        return paginated, next_offset, total
                except Exception as e:
                    logger.warning(f"AI search failed, falling back to legacy search: {e}")
            
        except Exception as e:
            logger.warning(f"Intent parsing failed, using legacy search: {e}")
        
        # Fallback to existing regex-based search
        logger.debug(f"Using legacy search fallback for: {query}")
        return await legacy_search_results(query, file_type, max_results, offset)


# Global instance
_integration: Optional[AISearchIntegration] = None


async def get_integration() -> AISearchIntegration:
    """Get or initialize the global AI search integration instance."""
    global _integration
    if _integration is None:
        _integration = AISearchIntegration()
    return _integration


async def ai_aware_search(query: str, file_type: Optional[str] = None,
                          max_results: int = 10, offset: int = 0) -> Tuple[List, Optional[int], int]:
    """Convenience function for AI-powered search with fallback.
    
    Drop-in replacement for get_search_results() with AI intelligence.
    """
    integration = await get_integration()
    return await integration.search(query, file_type, max_results, offset)
