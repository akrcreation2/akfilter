import random
from typing import Iterable, List
from .models import SearchResult


def sort_results(results: Iterable[SearchResult], mode: str = "relevance", seed: int = 0) -> List[SearchResult]:
    items = list(results)
    mode = mode.casefold().replace("-", "_")
    if mode in {"smallest", "size_asc", "size"}:
        return sorted(items, key=lambda x: (x.size_bytes is None, x.size_bytes or 0, -x.score))
    if mode in {"largest", "size_desc"}:
        return sorted(items, key=lambda x: (x.size_bytes is None, -(x.size_bytes or 0), -x.score))
    if mode == "year": return sorted(items, key=lambda x: (x.year is None, -(x.year or 0), -x.score))
    if mode == "quality": return sorted(items, key=lambda x: (x.quality is None, -(int((x.quality or "0").rstrip("p")) if (x.quality or "").rstrip("p").isdigit() else 0), -x.score))
    if mode == "random":
        result = list(items); random.Random(seed).shuffle(result); return result
    return sorted(items, key=lambda x: (-x.score, x.title.casefold(), x.file_id))
