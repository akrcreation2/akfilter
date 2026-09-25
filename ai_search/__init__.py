"""Isolated natural-language search subsystem for movie and series indexes.

This package has no imports from the production bot and is intentionally safe to
use in tests or a future adapter layer.
"""
from .models import SearchIntent, SearchResult
from .parser import QueryParser
from .search_engine import SearchEngine

__all__ = ["QueryParser", "SearchEngine", "SearchIntent", "SearchResult"]
