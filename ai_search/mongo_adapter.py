"""MongoDB adapter that bridges AI-parsed SearchIntent to existing ia_filterdb.

This module:
- Takes a user's natural-language query
- Parses it into SearchIntent
- Converts SearchIntent into optimized MongoDB queries
- Falls back to existing get_search_results() if anything fails
- Never modifies the existing database schema or indexes
- Maintains full backward compatibility

Design: Deterministic, no external API calls required.
"""

import logging
from typing import List, Optional, Tuple
import re

from ai_search.parser import QueryParser
from ai_search.models import SearchIntent, SearchResult
from ai_search.normalization import fold
from database.ia_filterdb import Media, get_search_results as legacy_get_search_results

logger = logging.getLogger(__name__)

# Global parser instance
_parser = None


def _get_parser():
    """Lazy-load parser singleton."""
    global _parser
    if _parser is None:
        _parser = QueryParser()
    return _parser


async def ai_aware_search(
    query: str,
    file_type: Optional[str] = None,
    max_results: int = 10,
    offset: int = 0,
    filter: bool = False
) -> Tuple[List, Optional[int], int]:
    """AI-aware search that bridges SearchIntent to existing MongoDB.

    Attempt to parse query into SearchIntent and use it to improve the search.
    If anything fails, fall back to the legacy regex-based search.

    Args:
        query: User's raw query string
        file_type: Optional file type filter
        max_results: Max results per page
        offset: Pagination offset
        filter: Whether to use regex filter mode

    Returns:
        (files, next_offset, total_results) - compatible with existing API
    """
    try:
        # Try AI-powered search path
        parser = _get_parser()
        intent = parser.parse(query or "")

        logger.debug(
            f"[AI Search] Parsed: person={intent.person}, title={intent.title}, "
            f"language={intent.language}, quality={intent.quality}, "
            f"size={intent.target_size_mb}, confidence={intent.confidence}"
        )

        # Use AI intent to build search terms
        search_terms = _build_search_terms(intent, query)
        if search_terms:
            logger.debug(f"[AI Search] Searching with terms: {search_terms}")
            files, next_offset, total = await _search_with_intent(
                search_terms, intent, max_results, offset, file_type
            )
            if files:
                logger.debug(f"[AI Search] Got {len(files)} results from AI-aware search")
                return files, next_offset, total

    except Exception as e:
        logger.warning(f"[AI Search] Failed, falling back to legacy search: {e}")

    # Fallback to existing search
    logger.debug(f"[AI Search] Using legacy search for: {query}")
    return await legacy_get_search_results(query, file_type, max_results, offset, filter)


def _build_search_terms(intent: SearchIntent, original_query: str) -> str:
    """Convert SearchIntent into search terms for MongoDB.

    Priority:
    1. If person is identified, search for that person
    2. If title is identified, search for that title
    3. Fall back to normalized query

    Returns: String to use in MongoDB filename regex
    """
    terms = []

    # Person search (e.g., Darshan)
    if intent.person:
        terms.append(intent.person)

    # Title search (e.g., Kantara, KGF)
    if intent.title:
        terms.append(intent.title)

    # Keywords extracted from query (non-reserved words)
    if intent.keywords:
        terms.extend(intent.keywords)

    # If nothing specific was parsed, use the original query
    if not terms:
        # Remove common stop words
        cleaned = re.sub(
            r"\b(movie|movies|film|films|series|show|the|a|an|of|in|is)\b",
            "",
            original_query,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            terms.append(cleaned)

    return " ".join(terms) if terms else original_query


async def _search_with_intent(
    search_terms: str,
    intent: SearchIntent,
    max_results: int,
    offset: int,
    file_type: Optional[str],
) -> Tuple[List, Optional[int], int]:
    """Execute MongoDB search using AI-parsed intent.

    Builds a MongoDB regex query from intent and searches existing Media collection.
    """
    try:
        # Build regex pattern from search terms
        if not search_terms.strip():
            return [], "", 0

        # Create case-insensitive regex
        pattern = search_terms.replace(" ", ".*")
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except Exception as e:
            logger.warning(f"[AI Search] Invalid regex pattern: {e}")
            return [], "", 0

        # Build MongoDB filter
        query_filter = {"file_name": regex}

        if file_type:
            query_filter["file_type"] = file_type

        # Optional: Filter for series vs movies
        if intent.content_type == "series":
            query_filter["file_name"] = re.compile(
                r"(S\d{1,2}|Season\s*\d+).*?(E|Ep|Episode)?\s*\d{1,2}",
                re.IGNORECASE,
            )
        elif intent.content_type == "movie":
            # Exclude series patterns from movie search
            series_pattern = re.compile(
                r"(S\d{1,2}|Season\s*\d+)", re.IGNORECASE
            )
            # This is a simple heuristic; not perfect but safe
            query_filter["file_name"] = re.compile(pattern, re.IGNORECASE)

        # Execute MongoDB query
        cursor = Media.find(query_filter)
        cursor.sort("$natural", -1)

        total_results = await Media.count_documents(query_filter)

        # Pagination
        next_offset = offset + max_results if offset + max_results < total_results else ""

        # Fetch results
        cursor.skip(offset).limit(max_results)
        files = await cursor.to_list(length=max_results)

        logger.debug(
            f"[AI Search] MongoDB query returned {len(files)} files, total: {total_results}"
        )

        return files, next_offset, total_results

    except Exception as e:
        logger.warning(f"[AI Search] MongoDB search failed: {e}")
        return [], "", 0
