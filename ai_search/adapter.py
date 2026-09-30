"""MongoDB adapter for the local AI search engine.

The existing Media collection remains the source of truth.  This adapter only
expands structured person queries into known movie-title candidates because the
current Media schema does not store actor/cast fields.
"""
import re
from typing import Dict, List, Tuple

from ai_search.entities import SearchProvider
from ai_search.filmography import match_person_title, titles_for_person
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
    def __init__(self, candidate_limit: int = 1000, person_term_chunk: int = 24):
        self.candidate_limit = candidate_limit
        # Keep Mongo regex documents reasonably small.  This matters for
        # filmography expansion, where one person can have many titles.
        self.person_term_chunk = max(8, int(person_term_chunk))

    @staticmethod
    def _pattern_terms(intent: SearchIntent) -> List[str]:
        terms = []
        if intent.person:
            # The production Media schema has no actor/cast field.  Search the
            # actor's known film titles instead of looking for the person's name
            # in every filename.
            terms.extend(title for title, _ in titles_for_person(intent.person))

        for value in [intent.title, *intent.keywords]:
            if value and len(str(value).strip()) >= 2:
                value = str(value).strip()
                if value.casefold() not in {x.casefold() for x in terms}:
                    terms.append(value)
        return terms

    @staticmethod
    def _build_regex(terms: List[str]):
        escaped = [re.escape(term) for term in terms if term]
        if not escaped:
            return None
        # Longest terms first reduces accidental partial matches such as "Arjun"
        # matching unrelated filenames before "Arjun" is actually intended.
        escaped.sort(key=len, reverse=True)
        return re.compile("|".join(escaped), re.IGNORECASE)

    async def search(self, intent: SearchIntent) -> List[SearchResult]:
        terms = self._pattern_terms(intent)
        if not terms:
            return []

        term_pattern = self._build_regex(terms)
        if term_pattern is None:
            return []

        try:
            # Import the production DB layer lazily so parser/ranker tests can run
            # without Telegram/Mongo dependencies installed.
            from database.ia_filterdb import Media
        except Exception:
            return []

        try:
            from info import USE_CAPTION_FILTER
        except Exception:
            # Test doubles and minimal environments may not provide info.py.
            USE_CAPTION_FILTER = True

        # The production schema indexes file_name, not actor/cast metadata.
        # Person searches therefore expand to film titles and query those titles
        # in small batches.  This is more reliable than one very large regex and
        # keeps the existing Media collection untouched.
        if intent.person:
            term_chunks = [
                terms[i:i + self.person_term_chunk]
                for i in range(0, len(terms), self.person_term_chunk)
            ]
        else:
            term_chunks = [terms]

        files_by_id: Dict[str, object] = {}
        for chunk in term_chunks:
            chunk_pattern = self._build_regex(chunk)
            if chunk_pattern is None:
                continue
            if USE_CAPTION_FILTER:
                query_filter = {
                    "$or": [
                        {"file_name": chunk_pattern},
                        {"caption": chunk_pattern},
                    ]
                }
            else:
                query_filter = {"file_name": chunk_pattern}
            try:
                cursor = Media.find(query_filter)
                chunk_files = await cursor.to_list(length=self.candidate_limit)
            except Exception:
                # One failed expansion must not break normal/legacy search.
                continue
            for file in chunk_files:
                file_id = str(getattr(file, "file_id", "") or getattr(file, "_id", ""))
                if file_id:
                    files_by_id[file_id] = file

            if len(files_by_id) >= self.candidate_limit:
                break

        files = list(files_by_id.values())[:self.candidate_limit]
        results: List[SearchResult] = []
        for file in files:
            file_name = str(getattr(file, "file_name", "") or "")
            caption = str(getattr(file, "caption", "") or "")
            searchable = f"{file_name} {caption}"
            folded = fold(searchable)

            matched_person_title = None
            matched_person_year = None
            if intent.person:
                matched_person_title, matched_person_year = match_person_title(searchable, intent.person)
                # For a person query, ignore a candidate that only matched one of
                # the generic keywords but is not actually in that person's known
                # filmography.
                if titles_for_person(intent.person) and not matched_person_title:
                    continue

            # Hard filters are applied only when the user explicitly requested them.
            if intent.language and intent.language.casefold() not in folded:
                continue

            filename_year = extract_year(searchable)
            effective_year = filename_year or matched_person_year
            if intent.year is not None and effective_year != intent.year:
                continue
            if intent.year_range:
                if effective_year is None or not (intent.year_range[0] <= effective_year <= intent.year_range[1]):
                    continue

            if intent.quality:
                quality_tokens = re.findall(
                    r"\b(?:4k|uhd|fhd|hd|1080p?|720p?|576p?|480p?|360p?)\b",
                    searchable,
                    re.I,
                )
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

            # The existing Media schema does not contain actor metadata.  Mark a
            # filmography match internally so ranking can still understand why the
            # result belongs to the requested person.
            if matched_person_title:
                metadata["matched_person"] = intent.person
                metadata["matched_person_title"] = matched_person_title
                metadata["actors"] = list(metadata.get("actors") or []) + [intent.person]
                if not metadata.get("year"):
                    metadata["year"] = matched_person_year

            metadata["_source_file"] = file

            result = SearchResult(
                file_id=str(getattr(file, "file_id", "")),
                title=file_name,
                language=metadata.get("language"),
                year=metadata.get("year") or effective_year,
                quality=metadata.get("quality"),
                resolution=metadata.get("resolution"),
                size_bytes=getattr(file, "file_size", None),
                season=metadata.get("season"),
                episode=metadata.get("episode"),
                metadata=metadata,
            )
            results.append(result)

        return results
