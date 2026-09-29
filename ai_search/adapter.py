"""MongoDB SearchProvider adapter for ai_search.SearchEngine.

Connects SearchIntent to existing MongoDB Media collection and ranking/grouping logic.
Designed to work alongside the existing regex-based search as a fallback.
"""
from typing import List, Optional
from database.ia_filterdb import Media
from ai_search.models import SearchIntent, SearchResult
from ai_search.entities import SearchProvider
import re


class MongoDBSearchProvider(SearchProvider):
    """Adapter that queries MongoDB Media collection based on SearchIntent.
    
    Converts SearchIntent filters into MongoDB queries and returns normalized SearchResult items.
    """
    def __init__(self):
        pass

    async def search(self, intent: SearchIntent) -> List[SearchResult]:
        """Convert SearchIntent into MongoDB query and return ranked results.
        
        Queries by:
        - title (if present)
        - keywords extracted from query
        Falls back to all results if no specific intent filters.
        
        Returns: List of SearchResult objects
        """
        # Build MongoDB filter based on intent
        query_filter = {}
        
        # Construct filename regex from intent
        search_terms = []
        if intent.title:
            search_terms.append(intent.title)
        if intent.person:
            search_terms.append(intent.person)
        if intent.keywords:
            search_terms.extend(intent.keywords)
        
        if search_terms:
            # Join terms with OR for filename search
            pattern = "|".join(re.escape(term) for term in search_terms)
            query_filter['file_name'] = re.compile(pattern, re.IGNORECASE)
        
        # Content type filter (movie vs series)
        if intent.content_type == "series":
            # Filter for series patterns: S01E01, Season 1 Episode 1, etc.
            query_filter['file_name'] = re.compile(r'(S\d{1,2}|Season\s*\d+).*?(E|Ep|Episode)?\d{1,2}', re.IGNORECASE)
        elif intent.content_type == "movie":
            # Exclude series patterns
            query_filter['$or'] = [
                {'file_name': {'$not': re.compile(r'(S\d{1,2}|Season\s*\d+)', re.IGNORECASE)}},
            ]
        
        try:
            # Query MongoDB
            cursor = Media.find(query_filter)
            # Get all matching files (limit to 1000 to avoid huge result sets)
            files = await cursor.to_list(length=1000)
            
            # Convert to SearchResult objects
            results = []
            for file in files:
                title = getattr(file, 'file_name', '')
                size_bytes = getattr(file, 'file_size', None)
                
                result = SearchResult(
                    file_id=getattr(file, 'file_id', ''),
                    title=title,
                    size_bytes=size_bytes,
                    metadata={
                        'caption': getattr(file, 'caption', ''),
                        'mime_type': getattr(file, 'mime_type', ''),
                        'file_type': getattr(file, 'file_type', ''),
                    }
                )
                results.append(result)
            
            return results
        except Exception as e:
            # Log error but return empty list (non-fatal)
            return []
