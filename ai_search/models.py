from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SearchIntent:
    original_query: str
    normalized_query: str = ""
    title: Optional[str] = None
    person: Optional[str] = None
    person_type: Optional[str] = None
    language: Optional[str] = None
    year: Optional[int] = None
    year_range: Optional[Tuple[int, int]] = None
    quality: Optional[str] = None
    resolution: Optional[Tuple[int, int]] = None
    target_size_mb: Optional[float] = None
    content_type: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    keywords: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    sort_order: str = "relevance"
    corrections: List[Tuple[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    known: Dict[str, Any] = field(default_factory=dict)
    inferred: Dict[str, Any] = field(default_factory=dict)
    unknown: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    file_id: str
    title: str
    language: Optional[str] = None
    year: Optional[int] = None
    quality: Optional[str] = None
    resolution: Optional[Tuple[int, int]] = None
    size_bytes: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GroupedResult:
    title: str
    files: List[SearchResult] = field(default_factory=list)
    seasons: Dict[int, Dict[int, List[SearchResult]]] = field(default_factory=dict)
