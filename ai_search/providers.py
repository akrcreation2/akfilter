"""Public provider interfaces for future database and metadata adapters."""
from .entities import EntityCandidate, MetadataProvider, SearchProvider, candidate_is_person

__all__ = ["EntityCandidate", "MetadataProvider", "SearchProvider", "candidate_is_person"]
