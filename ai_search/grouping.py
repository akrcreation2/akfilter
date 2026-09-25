import re
from collections import defaultdict
from typing import Dict, Iterable, List
from .models import GroupedResult, SearchResult


def series_parts(result: SearchResult):
    season = result.season if result.season is not None else 0
    episode = result.episode if result.episode is not None else 0
    return season, episode


def group_results(results: Iterable[SearchResult]) -> List[GroupedResult]:
    groups: Dict[str, GroupedResult] = {}
    for result in results:
        key = re.sub(r"\s+", " ", result.title.casefold()).strip()
        group = groups.setdefault(key, GroupedResult(title=result.title))
        group.files.append(result)
        if result.season is not None or result.episode is not None:
            group.seasons.setdefault(result.season or 0, {}).setdefault(result.episode or 0, []).append(result)
    output = list(groups.values())
    for group in output:
        group.files.sort(key=lambda x: ((x.size_bytes is None), x.size_bytes or 0, x.file_id))
        for season in group.seasons.values():
            for files in season.values(): files.sort(key=lambda x: ((x.size_bytes is None), x.size_bytes or 0, x.file_id))
        group.seasons = dict(sorted(group.seasons.items()))
        group.seasons = {s: dict(sorted(e.items())) for s, e in group.seasons.items()}
    return sorted(output, key=lambda x: x.title.casefold())
