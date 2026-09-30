"""MongoDB adapter for the isolated AI search engine.

The adapter deliberately returns normalized SearchResult objects while keeping the
original Mongo/umongo document attached internally so the existing Telegram UI can
continue to use file.file_id, file.file_name, file.file_size, etc.
"""
import re
from typing import List

from ai_search.entities import SearchProvider
from ai_search.metadata import (
    extract_episode,
    extract_season_episode,
    extract_year,
    normalize_media_metadata,
    normalize_quality,
)
from ai_search.models import SearchIntent, SearchResult
from ai_search.normalization import fold


class MongoDBSearchProvider(SearchProvider):
    def __init__(self, candidate_limit: int = 1000):
        self.candidate_limit = candidate_limit

    @staticmethod
    def _pattern_terms(intent: SearchIntent) -> List[str]:
        terms = []
        for value in [intent.title, intent.person, *intent.keywords]:
            if value and len(str(value).strip()) >= 2:
                value = str(value).strip()
                if value.casefold() not in {x.casefold() for x in terms}:
                    terms.append(value)
        return terms

    async def search(self, intent: SearchIntent) -> List[SearchResult]:
        terms = self._pattern_terms(intent)
        if not terms:
            return []

        escaped = [re.escape(term) for term in terms]
        term_pattern = re.compile("|".join(escaped), re.IGNORECASE)
        query_filter = {"file_name": term_pattern}

        # Keep caption searching compatible with repositories that store useful
        # searchable text there, but don't require a caption field to exist.
        try:
            # Import the production DB layer lazily so the isolated parser/ranker
            # tests can run without Telegram/Mongo dependencies installed.
            from database.ia_filterdb import Media
            cursor = Media.find(query_filter)
            files = await cursor.to_list(length=self.candidate_limit)
        except Exception:
            return []

        results: List[SearchResult] = []
        for file in files:
            file_name = str(getattr(file, "file_name", "") or "")
            caption = str(getattr(file, "caption", "") or "")
            searchable = f"{file_name} {caption}"
            folded = fold(searchable)

            # Hard filters are applied only when the user explicitly requested them.
            if intent.language and intent.language.casefold() not in folded:
                continue
            if intent.year is not None and str(intent.year) not in searchable:
                continue
            if intent.year_range:
                years = re.findall(r"\b(?:19|20)\d{2}\b", searchable)
                if years and not any(intent.year_range[0] <= int(y) <= intent.year_range[1] for y in years):
                    continue
            if intent.quality:
                quality_tokens = re.findall(r"\b(?:4k|uhd|fhd|hd|1080p?|720p?|576p?|480p?|360p?)\b", searchable, re.I)
                normalized = [normalize_quality(x) for x in quality_tokens]
                if intent.quality not in normalized:
                    continue
            if intent.season is not None:
                season, _ = extract_season_episode(searchable)
                if season != intent.season:
                    continue
            if intent.episode is not None:
                episode = extract_episode(searchable)
                if episode != intent.episode:
                    continue

            metadata = normalize_media_metadata({
                "file_name": file_name,
                "caption": caption,
                "mime_type": getattr(file, "mime_type", ""),
                "file_type": getattr(file, "file_type", ""),
                "actors": getattr(file, "actors", []) or [],
                "cast": getattr(file, "cast", []) or [],
                "themes": getattr(file, "themes", []) or [],
            })
            metadata["_source_file"] = file

            result = SearchResult(
                file_id=str(getattr(file, "file_id", "")),
                title=file_name,
                language=metadata.get("language"),
                year=metadata.get("year") or extract_year(searchable),
                quality=metadata.get("quality"),
                resolution=metadata.get("resolution"),
                size_bytes=getattr(file, "file_size", None),
                season=metadata.get("season"),
                episode=metadata.get("episode"),
                metadata=metadata,
            )
            results.append(result)

        return results
