from typing import Iterable, List, Optional
from .entities import MetadataProvider, SearchProvider
from .models import SearchIntent, SearchResult
from .ranking import rank_results
from .sorting import sort_results

class SearchEngine:
    def __init__(self, provider: SearchProvider, metadata_provider: Optional[MetadataProvider] = None):
        self.provider = provider
        self.metadata_provider = metadata_provider

    async def search(self, intent: SearchIntent, limit: Optional[int] = None) -> List[SearchResult]:
        try:
            if self.metadata_provider:
                intent = await self.metadata_provider.resolve(intent)
            candidates = await self.provider.search(intent)
            ranked = rank_results(candidates, intent)
            ranked = sort_results(ranked, intent.sort_order)
            return ranked[:limit] if limit else ranked
        except Exception:
            # An adapter can log this at its boundary; search failures are non-fatal.
            return []
