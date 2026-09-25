import random
from difflib import SequenceMatcher
from typing import Iterable, List
from .config import RankingWeights
from .metadata import normalize_media_metadata
from .models import SearchIntent, SearchResult
from .normalization import fold


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, fold(a), fold(b)).ratio() if a and b else 0.0


def rank_result(result: SearchResult, intent: SearchIntent, weights: RankingWeights = RankingWeights()) -> float:
    score = 0.0
    score += weights.title * similarity(intent.title or intent.normalized_query, result.title)
    person_text = " ".join(map(str, result.metadata.get("actors", []) + result.metadata.get("cast", [])))
    if intent.person: score += weights.person * similarity(intent.person, person_text)
    if intent.language: score += weights.language * (1 if fold(intent.language) == fold(result.language or "") else 0)
    if intent.year is not None: score += weights.year * (1 if intent.year == result.year else 0)
    if intent.year_range and result.year: score += weights.year * (1 if intent.year_range[0] <= result.year <= intent.year_range[1] else 0)
    if intent.quality and result.quality: score += weights.quality * (1 if intent.quality == result.quality else similarity(intent.quality, result.quality))
    if intent.target_size_mb and result.size_bytes:
        distance = abs(result.size_bytes / 1024**2 - intent.target_size_mb) / max(intent.target_size_mb, 1)
        score += weights.size * max(0.0, 1.0 - distance)
    if intent.season is not None: score += weights.season * (1 if intent.season == result.season else 0)
    if intent.episode is not None: score += weights.episode * (1 if intent.episode == result.episode else 0)
    score += weights.semantic * sum(1 for theme in intent.themes if theme in result.metadata.get("themes", []))
    return round(score, 6)


def rank_results(results: Iterable[SearchResult], intent: SearchIntent, weights=RankingWeights()) -> List[SearchResult]:
    ranked = []
    for result in results:
        result.metadata = normalize_media_metadata(result.metadata)
        result.score = rank_result(result, intent, weights)
        ranked.append(result)
    return sorted(ranked, key=lambda item: (-item.score, fold(item.title), item.file_id))
