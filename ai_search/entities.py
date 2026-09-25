from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
from .models import SearchIntent


@dataclass(frozen=True)
class EntityCandidate:
    name: str
    entity_type: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = None


class MetadataProvider:
    async def search_titles(self, query: str) -> Iterable[EntityCandidate]:
        return []

    async def search_person(self, query: str) -> Iterable[EntityCandidate]:
        return []

    async def get_title_details(self, title: str) -> Optional[Dict[str, Any]]:
        return None

    async def resolve(self, intent: SearchIntent) -> SearchIntent:
        return intent


class SearchProvider:
    async def search(self, intent: SearchIntent):
        raise NotImplementedError


def candidate_is_person(candidate: EntityCandidate) -> bool:
    return candidate.entity_type.casefold() in {"person", "actor", "actress", "director"}
