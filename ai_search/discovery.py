"""
Free movie discovery layer.

No paid AI API is required.
- Uses a lightweight rule-based natural-language parser.
- Resolves people/movies through public Wikimedia/Wikidata endpoints when available.
- Caches discoveries locally so repeated searches do not hit the network.
- This module only discovers movie titles; it does NOT query the bot's file database.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import List, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

CACHE_DIR = os.getenv("AI_DISCOVERY_CACHE_DIR", "ai_search/cache")
CACHE_TTL = int(os.getenv("AI_DISCOVERY_CACHE_TTL", "604800"))
USER_AGENT = "AKFilter-FreeMovieDiscovery/1.0"


@dataclass
class DiscoveredMovie:
    title: str
    year: Optional[int] = None
    source: str = "public-metadata"


def _cache_path(key: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", key.lower())[:180]
    return os.path.join(CACHE_DIR, safe + ".json")


def _get_json(url: str):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


def _cached(key: str):
    path = _cache_path(key)
    try:
        if time.time() - os.path.getmtime(path) > CACHE_TTL:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(key: str, value):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(key), "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)


def _wiki_search_person(name: str):
    cached = _cached("person_" + name)
    if cached is not None:
        return cached

    url = (
        "https://en.wikipedia.org/w/api.php?action=query&format=json"
        "&list=search&srnamespace=0&srlimit=5&srsearch="
        + quote(name)
    )
    try:
        data = _get_json(url)
        results = [x["title"] for x in data.get("query", {}).get("search", [])]
        _save_cache("person_" + name, results)
        return results
    except Exception:
        return []


def _wiki_page_text(title: str):
    key = "page_" + title
    cached = _cached(key)
    if cached is not None:
        return cached

    url = (
        "https://en.wikipedia.org/w/api.php?action=query&format=json"
        "&prop=extracts&explaintext=1&exsectionformat=plain&redirects=1&titles="
        + quote(title)
    )
    try:
        data = _get_json(url)
        pages = data.get("query", {}).get("pages", {})
        text = next(iter(pages.values())).get("extract", "")
        _save_cache(key, text)
        return text
    except Exception:
        return ""


def _extract_year(text: str, title: str):
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text[:500])
    if years:
        return int(years[0])
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", title)
    return int(years[0]) if years else None


def discover_person_movies(person: str, limit: int = 40) -> List[DiscoveredMovie]:
    """
    Best-effort public discovery. It deliberately returns movie names,
    not file/database results.
    """
    candidates = _wiki_search_person(person)
    movies: List[DiscoveredMovie] = []

    # Search result pages often include filmography pages.
    for candidate in candidates:
        low = candidate.lower()
        if "filmography" not in low and "film" not in low and candidate.lower() != person.lower():
            continue

        text = _wiki_page_text(candidate)
        # Extract common table-like lines containing a year.
        for line in text.splitlines():
            line = re.sub(r"\[[^\]]+\]", "", line).strip()
            m = re.search(r"\b(19\d{2}|20\d{2})\b", line)
            if not m:
                continue
            year = int(m.group(1))
            # Keep a conservative title token from markdown/table text.
            cleaned = re.sub(r"^\s*[\|\*\-\d.\s]+", "", line)
            cleaned = re.split(r"\s{2,}|\|", cleaned)[0].strip()
            if 2 <= len(cleaned) <= 100 and cleaned.lower() not in {person.lower(), "year"}:
                movies.append(DiscoveredMovie(cleaned, year))

        if len(movies) >= limit:
            break

    # Deduplicate while preserving order.
    seen = set()
    out = []
    for m in movies:
        key = (re.sub(r"\W+", "", m.title.lower()), m.year)
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
        if len(out) >= limit:
            break
    return out


def discover_movies_from_query(query: str, limit: int = 40) -> List[DiscoveredMovie]:
    """
    Generic free discovery entry point.

    This intentionally focuses on identifying a likely person query.
    Existing application code can pass a parsed person/entity here.
    """
    q = query.strip()
    q = re.sub(r"\b(show|give|list|all|movies?|films?)\b", " ", q, flags=re.I)
    q = re.sub(r"\s+", " ", q).strip()

    # Common Kannada/English person-query patterns.
    person = re.sub(r"\b(movie|movies|film|films|list|all|acted|acting)\b", " ", q, flags=re.I)
    person = re.sub(r"\s+", " ", person).strip()

    if not person or len(person) < 2:
        return []

    return discover_person_movies(person, limit=limit)


# ---------------------------------------------------------------------------
# Compatibility API used by the existing ai-search phase-1 branch.
# Keep these names stable so Pyrogram can load the plugin safely.
# ---------------------------------------------------------------------------

MovieCandidate = DiscoveredMovie


def _parse_json_candidates(payload: str) -> List[MovieCandidate]:
    """Parse a small, deterministic JSON movie list from a public source/adapter."""
    try:
        data = json.loads(payload)
    except Exception:
        return []
    raw = data.get("movies", []) if isinstance(data, dict) else []
    out = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        year = item.get("year")
        try:
            year = int(year) if year is not None else None
        except (TypeError, ValueError):
            year = None
        key = (title.casefold(), year)
        if key in seen:
            continue
        seen.add(key)
        out.append(MovieCandidate(title=title, year=year))
    return out


def looks_like_discovery_query(query: str) -> bool:
    """Return True for requests that ask the bot to discover movie titles."""
    q = (query or "").strip().lower()
    if not q:
        return False

    # A direct file query should stay on the proven database path.
    if re.search(r"\b(2160p|1080p|720p|576p|480p|360p|hdrip|webrip|web[- ]dl|bluray|blu[- ]ray|x264|x265|hevc|season|episode|s\d{1,2}e\d{1,2})\b", q):
        return False

    discovery_terms = (
        "movies", "films", "filmography", "acted", "acting", "actor", "actress",
        "hero", "heroine", "star", "all movies", "list movies", "movie list",
        "movies of", "films of", "acted together", "together", "film with",
        "dubbed", "dubbing", "kannada movies", "telugu movies", "tamil movies",
        "malayalam movies", "this year", "which movies", "what movies",
        "movies where", "movie where", "song in", "songs in",
    )
    if any(term in q for term in discovery_terms):
        return True

    # Long natural-language requests are candidates for discovery, unless
    # they clearly contain file-quality search syntax above.
    return len(q.split()) >= 12


def _extract_person_from_query(query: str) -> str:
    """Conservative person extraction for the free/public discovery path."""
    q = re.sub(r"\s+", " ", (query or "").strip())

    # Remove common request words, but preserve a multi-word person name.
    q = re.sub(
        r"\b(find|show|give|list|all|the|movies?|films?|filmography|"
        r"acted|acting|actor|actress|hero|heroine|movie|movies|"
        r"which|what|where|together|with|of|for|in|from|"
        r"kannada|kannada-language|telugu|tamil|malayalam|hindi|"
        r"this year|after \d{4}|before \d{4})\b",
        " ",
        q,
        flags=re.I,
    )
    q = re.sub(r"\s+", " ", q).strip(" ,.-?")

    # Strip obvious relationship tails.
    q = re.split(
        r"\b(?:and|who|that|where|between|with|along with)\b",
        q,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" ,.-?")

    return q


async def discover_movies_with_timeout(query: str, limit: int = 40) -> List[MovieCandidate]:
    """
    Async adapter expected by plugins/pm_filter.py.

    Network work is executed in a worker thread so it never blocks the
    Pyrogram event loop.
    """
    import asyncio

    if not looks_like_discovery_query(query):
        return []

    person = _extract_person_from_query(query)
    if not person:
        return []

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(discover_person_movies, person, limit),
            timeout=15,
        )
    except Exception:
        return []


def discover_movies(query: str, limit: int = 40) -> List[MovieCandidate]:
    """Synchronous compatibility entry point."""
    if not looks_like_discovery_query(query):
        return []
    person = _extract_person_from_query(query)
    return discover_person_movies(person, limit=limit) if person else []
