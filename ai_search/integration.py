"""Safe bridge between the AI search subsystem and the existing bot search API."""
import logging
from typing import List, Optional, Tuple

from ai_search import QueryParser, SearchEngine
from ai_search.adapter import MongoDBSearchProvider

logger = logging.getLogger(__name__)


class AISearchIntegration:
    """AI-first search with a guaranteed legacy fallback.

    The public return value intentionally matches get_search_results():
    (Media documents, next_offset, total_results).
    """

    def __init__(self):
        self.parser = QueryParser()
        self.provider = MongoDBSearchProvider()
        self.engine = SearchEngine(self.provider)
        self.min_confidence = 0.45

    @staticmethod
    def _source_files(results):
        files = []
        seen = set()
        for result in results:
            file = result.metadata.get("_source_file") if result.metadata else None
            if file is None:
                continue
            file_id = str(getattr(file, "file_id", result.file_id))
            if file_id in seen:
                continue
            seen.add(file_id)
            files.append(file)
        return files

    async def search(
        self,
        query: str,
        file_type: Optional[str] = None,
        max_results: int = 10,
        offset: int = 0,
        filter: bool = False,
    ) -> Tuple[List, Optional[int], int]:
        from database.ia_filterdb import get_search_results as legacy_search_results
        query = (query or "").strip()
        if not query:
            return await legacy_search_results(query, file_type, max_results, offset, filter)

        try:
            intent = self.parser.parse(query)
            logger.info(
                "AI search intent: query=%r title=%r person=%r language=%r year=%r "
                "quality=%r season=%r episode=%r confidence=%.2f",
                query, intent.title, intent.person, intent.language, intent.year,
                intent.quality, intent.season, intent.episode, intent.confidence,
            )

            # Only let clearly understood queries enter the AI path. Everything
            # else immediately uses the repository's proven legacy search.
            if intent.confidence >= self.min_confidence and (intent.title or intent.person or intent.keywords):
                ai_results = await self.engine.search(intent, limit=None)
                ai_files = self._source_files(ai_results)

                if file_type:
                    ai_files = [
                        f for f in ai_files
                        if getattr(f, "file_type", None) == file_type
                    ]

                # Engine sorting is already relevance-aware; preserve that order.
                if ai_files:
                    total = len(ai_files)
                    page = ai_files[offset:offset + max_results]
                    next_offset = offset + max_results if offset + max_results < total else ""
                    return page, next_offset, total

        except Exception:
            logger.exception("AI search failed; falling back to legacy search")

        return await legacy_search_results(query, file_type, max_results, offset, filter)


_integration: Optional[AISearchIntegration] = None


async def get_integration() -> AISearchIntegration:
    global _integration
    if _integration is None:
        _integration = AISearchIntegration()
    return _integration


async def ai_aware_search(
    query: str,
    file_type: Optional[str] = None,
    max_results: int = 10,
    offset: int = 0,
    filter: bool = False,
) -> Tuple[List, Optional[int], int]:
    """Drop-in compatible replacement for database.ia_filterdb.get_search_results."""
    integration = await get_integration()
    return await integration.search(query, file_type, max_results, offset, filter)
