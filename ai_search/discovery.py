"""
External movie discovery layer.

Important design rule:
    This module NEVER reads the bot's Media/file database to discover movies.

The discovery pipeline is intentionally API-key free:
    1. Wikidata entity search / SPARQL for structured people + movie relations.
    2. Wikipedia search for public movie/filmography pages.
    3. DuckDuckGo HTML search as a broad web-search fallback.

Only after the user clicks a discovered movie button does plugins/pm_filter.py
query the bot's own Media collection.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

CACHE_DIR = os.getenv("AI_DISCOVERY_CACHE_DIR", "ai_search/cache")
CACHE_TTL = int(os.getenv("AI_DISCOVERY_CACHE_TTL", "604800"))
NETWORK_TIMEOUT = float(os.getenv("AI_DISCOVERY_NETWORK_TIMEOUT", "8"))
USER_AGENT = os.getenv(
    "AI_DISCOVERY_USER_AGENT",
    "AKFilterMovieDiscovery/2.0 (+https://github.com/akrcreation2/akfilter)",
)
MAX_RESULTS = 60


@dataclass
class MovieCandidate:
    title: str
    year: Optional[int] = None
    source: str = "public-web"


# Backward-compatible name used by older code.
DiscoveredMovie = MovieCandidate


def _cache_path(key: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", key.lower())[:180]
    return os.path.join(CACHE_DIR, safe + ".json")


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
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
    except Exception:
        pass


def _get_json(url: str, params: Optional[dict] = None, timeout: float = NETWORK_TIMEOUT):
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _get_text(url: str, params: Optional[dict] = None, timeout: float = NETWORK_TIMEOUT):
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _dedupe(movies: Iterable[MovieCandidate], limit: int = MAX_RESULTS) -> List[MovieCandidate]:
    out: List[MovieCandidate] = []
    seen = set()
    for movie in movies:
        title = re.sub(r"\s+", " ", str(movie.title or "")).strip(" -|•")
        if not title or len(title) < 2 or len(title) > 120:
            continue
        if re.fullmatch(r"\d{4}", title):
            continue
        year = None
        try:
            if movie.year:
                y = int(movie.year)
                if 1880 <= y <= 2100:
                    year = y
        except (TypeError, ValueError):
            pass
        key = (re.sub(r"[^a-z0-9]+", "", title.casefold()), year)
        if key in seen:
            continue
        seen.add(key)
        out.append(MovieCandidate(title=title, year=year, source=movie.source))
        if len(out) >= limit:
            break
    return out


def _year_from_text(text: str) -> Optional[int]:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")
    for value in years:
        year = int(value)
        if 1880 <= year <= 2100:
            return year
    return None


# ---------------------------------------------------------------------------
# Wikidata
# ---------------------------------------------------------------------------

_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


def _wikidata_entities_sync(text: str, limit: int = 5):
    key = "wd_entities_" + text
    cached = _cached(key)
    if cached is not None:
        return cached
    try:
        data = _get_json(
            _WIKIDATA_API,
            {
                "action": "wbsearchentities",
                "search": text,
                "language": "en",
                "uselang": "en",
                "format": "json",
                "limit": str(limit),
            },
        )
        values = []
        for item in data.get("search", []):
            qid = item.get("id")
            label = item.get("label")
            desc = item.get("description") or ""
            if qid and label:
                values.append({"id": qid, "label": label, "description": desc})
        _save_cache(key, values)
        return values
    except Exception:
        return []


def _looks_like_person_entity(item: dict, wanted: str) -> bool:
    desc = (item.get("description") or "").casefold()
    label = (item.get("label") or "").casefold()
    wanted_fold = wanted.casefold().strip()
    person_words = ("actor", "actress", "film actor", "film actress", "singer", "director", "producer", "screenwriter", "cinema")
    return (
        any(word in desc for word in person_words)
        or label == wanted_fold
        or label.replace(" ", "") == wanted_fold.replace(" ", "")
    )


def _resolve_person_sync(name: str) -> Optional[Tuple[str, str]]:
    candidates = _wikidata_entities_sync(name, limit=7)
    for item in candidates:
        if _looks_like_person_entity(item, name):
            return item["id"], item["label"]
    return None



def _resolve_language_qid_sync(language: str) -> Optional[str]:
    items = _wikidata_entities_sync(language, limit=6)
    for item in items:
        desc = (item.get("description") or "").casefold()
        label = (item.get("label") or "").casefold()
        if "language" in desc or label == language.casefold():
            qid = item.get("id")
            if qid and re.fullmatch(r"Q\d+", qid):
                return qid
    return None


def _wikidata_movies_by_filters_sync(
    year: Optional[int] = None,
    year_range: Optional[Tuple[int, int]] = None,
    language: Optional[str] = None,
    limit: int = 50,
) -> List[MovieCandidate]:
    """Discover films from Wikidata when there is no person constraint."""
    if year is None and not year_range and not language:
        return []
    filters = []
    if year is not None:
        filters.append(f"FILTER(YEAR(?date) = {int(year)})")
    elif year_range:
        filters.append(
            f"FILTER(YEAR(?date) >= {int(year_range[0])} && YEAR(?date) <= {int(year_range[1])})"
        )
    language_filter = ""
    if language:
        lang_qid = _resolve_language_qid_sync(language)
        if lang_qid:
            language_filter = f"?film wdt:P407 wd:{lang_qid}."
    sparql = f"""
    SELECT ?film ?filmLabel (MIN(?date) AS ?firstDate) WHERE {{
      ?film wdt:P31/wdt:P279* wd:Q11424;
            wdt:P577 ?date.
      {language_filter}
      {' '.join(filters)}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\". }}
    }}
    GROUP BY ?film ?filmLabel
    ORDER BY DESC(?firstDate)
    LIMIT {int(limit)}
    """
    key = "wd_filter_films_" + str(abs(hash(sparql)))
    cached = _cached(key)
    if cached is not None:
        return [MovieCandidate(**x) for x in cached]
    try:
        data = _get_json(_WIKIDATA_SPARQL, {"query": sparql, "format": "json"}, timeout=NETWORK_TIMEOUT + 4)
        out = []
        for row in data.get("results", {}).get("bindings", []):
            title = row.get("filmLabel", {}).get("value")
            date = row.get("firstDate", {}).get("value", "")
            if title:
                out.append(MovieCandidate(title=title, year=_year_from_text(date), source="wikidata"))
        out = _dedupe(out, limit)
        _save_cache(key, [x.__dict__ for x in out])
        return out
    except Exception:
        return []

def _wikidata_films_sync(
    qids: Sequence[str],
    year: Optional[int] = None,
    year_range: Optional[Tuple[int, int]] = None,
    language: Optional[str] = None,
    limit: int = 80,
) -> List[MovieCandidate]:
    if not qids:
        return []
    values = " ".join(f"wd:{qid}" for qid in qids if re.fullmatch(r"Q\d+", qid))
    if not values:
        return []

    # P161 = cast member, P577 = publication/release date, P407 = language of work.
    # For multiple people, requiring all P161 values gives the desired
    # "acted together" intersection without touching the bot database.
    person_filters = "\n".join(f"?film wdt:P161 wd:{qid}." for qid in qids if re.fullmatch(r"Q\d+", qid))
    filters = []
    if year is not None:
        filters.append(f"FILTER(YEAR(?date) = {int(year)})")
    elif year_range:
        filters.append(
            f"FILTER(YEAR(?date) >= {int(year_range[0])} && YEAR(?date) <= {int(year_range[1])})"
        )

    language_filter = ""
    if language:
        # Resolve language label to a Wikidata entity. If resolution fails we
        # leave language filtering to the broad web fallback instead of guessing.
        lang_item = _wikidata_entities_sync(language, limit=5)
        lang_qid = None
        for item in lang_item:
            desc = (item.get("description") or "").casefold()
            label = (item.get("label") or "").casefold()
            if "language" in desc or label == language.casefold():
                lang_qid = item.get("id")
                break
        if lang_qid and re.fullmatch(r"Q\d+", lang_qid):
            language_filter = f"?film wdt:P407 wd:{lang_qid}."

    sparql = f"""
    SELECT ?film ?filmLabel (MIN(?date) AS ?firstDate) WHERE {{
      {person_filters}
      ?film wdt:P577 ?date.
      {language_filter}
      ?film wdt:P31/wdt:P279* wd:Q11424.
      {' '.join(filters)}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\". }}
    }}
    GROUP BY ?film ?filmLabel
    ORDER BY DESC(?firstDate)
    LIMIT {int(limit)}
    """
    key = "wd_films_" + str(abs(hash(sparql)))
    cached = _cached(key)
    if cached is not None:
        return [MovieCandidate(**x) for x in cached]
    try:
        data = _get_json(_WIKIDATA_SPARQL, {"query": sparql, "format": "json"}, timeout=NETWORK_TIMEOUT + 4)
        out = []
        for row in data.get("results", {}).get("bindings", []):
            title = row.get("filmLabel", {}).get("value")
            date = row.get("firstDate", {}).get("value", "")
            if title:
                out.append(MovieCandidate(title=title, year=_year_from_text(date), source="wikidata"))
        out = _dedupe(out, limit)
        _save_cache(key, [x.__dict__ for x in out])
        return out
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Wikipedia + DuckDuckGo broad web search
# ---------------------------------------------------------------------------


def _wikipedia_search_sync(query: str, limit: int = 10) -> List[str]:
    key = "wiki_search_" + query
    cached = _cached(key)
    if cached is not None:
        return cached
    try:
        data = _get_json(
            _WIKIPEDIA_API,
            {
                "action": "query", "format": "json", "list": "search",
                "srnamespace": "0", "srlimit": str(limit), "srsearch": query,
            },
        )
        results = [x.get("title", "") for x in data.get("query", {}).get("search", []) if x.get("title")]
        _save_cache(key, results)
        return results
    except Exception:
        return []


class _DDGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_result = False
        self.current = []
        self.results: List[Tuple[str, str]] = []
        self.href = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        cls = attrs.get("class", "")
        if tag == "a" and "result__a" in cls:
            self.in_result = True
            self.current = []
            self.href = attrs.get("href", "")

    def handle_data(self, data):
        if self.in_result:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_result:
            title = html.unescape("".join(self.current)).strip()
            if title:
                self.results.append((title, self.href))
            self.in_result = False
            self.current = []
            self.href = ""


def _duckduckgo_search_sync(query: str, limit: int = 10) -> List[Tuple[str, str]]:
    key = "ddg_" + query
    cached = _cached(key)
    if cached is not None:
        return [tuple(x) for x in cached]
    try:
        raw = _get_text(
            "https://html.duckduckgo.com/html/",
            {"q": query, "kl": "us-en"},
            timeout=NETWORK_TIMEOUT,
        )
        parser = _DDGParser()
        parser.feed(raw)
        results = parser.results[:limit]
        _save_cache(key, results)
        return results
    except Exception:
        return []


def _movie_from_search_title(title: str) -> Optional[MovieCandidate]:
    text = re.sub(r"\s+", " ", html.unescape(title)).strip()
    # Remove common search-engine / encyclopedia suffixes.
    text = re.sub(r"\s*[|–-]\s*(Wikipedia|IMDb|The Movie Database|TMDB).*$", "", text, flags=re.I)
    text = re.sub(r"\s+filmography.*$", "", text, flags=re.I)
    text = re.sub(r"\s+movies?$", "", text, flags=re.I)
    year = _year_from_text(text)
    # Don't treat a pure person/topic page as a movie.
    low = text.casefold()
    if any(x in low for x in ("filmography", "actor", "actress", "singer", "director", "list of films")):
        return None
    if len(text) < 2 or len(text) > 110:
        return None
    return MovieCandidate(title=re.sub(r"\s*\(?(?:19|20)\d{2}\)?$", "", text).strip(), year=year, source="web-search")


def _wikipedia_movie_candidates_sync(query: str, limit: int = 30) -> List[MovieCandidate]:
    titles = _wikipedia_search_sync(query, limit=12)
    out = []
    for title in titles:
        year = _year_from_text(title)
        clean = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", title).strip()
        if clean and not any(x in clean.casefold() for x in ("filmography", "list of", "actor", "actress")):
            out.append(MovieCandidate(clean, year, "wikipedia"))
    return _dedupe(out, limit)


# ---------------------------------------------------------------------------
# Query understanding without a paid AI API
# ---------------------------------------------------------------------------

_DISCOVERY_WORDS = {
    "movie", "movies", "film", "films", "cinema", "filmography", "acted", "acting",
    "actor", "actress", "hero", "heroine", "cast", "starring", "together", "dubbed",
    "dubbing", "song", "songs", "language", "year", "released", "release", "find",
    "show", "list", "all", "which", "what", "where", "this", "current", "latest",
    "after", "before", "between", "with", "and", "or", "in", "from", "the", "for",
}

_FILE_WORDS = re.compile(
    r"\b(?:2160p|1080p|720p|576p|480p|360p|4k|uhd|fhd|hdrip|webrip|web[- ]?dl|bluray|blu[- ]?ray|brrip|dvdrip|x264|x265|h264|h265|hevc|mkv|mp4|avi|mb|gb|season|episode|s\d{1,2}e\d{1,2})\b",
    re.I,
)


def looks_like_discovery_query(query: str) -> bool:
    """Decide whether the message deserves an external discovery attempt.

    Normal movie/person text is discovery-first. Technical file queries stay on
    the existing fast Media search path. If discovery finds nothing, the caller
    can safely fall back to the legacy search.
    """
    q = re.sub(r"\s+", " ", (query or "").strip())
    if not q:
        return False
    if _FILE_WORDS.search(q):
        return False
    if len(q.split()) >= 2:
        return True
    # One-word titles can also be discovered, but commands/very generic words
    # should remain on the old path.
    return q.casefold() not in {"hi", "hello", "help", "start", "search", "movie", "movies"}


def _query_constraints(query: str):
    q = re.sub(r"\s+", " ", query or "").strip()
    year = None
    year_range = None
    m = re.search(r"\b(19\d{2}|20\d{2})\s*(?:-|to|–)\s*(19\d{2}|20\d{2})\b", q, re.I)
    if m:
        year_range = (int(m.group(1)), int(m.group(2)))
    else:
        m = re.search(r"\b(19\d{2}|20\d{2})\b", q)
        if m:
            year = int(m.group(1))
        elif re.search(r"\b(this|current)\s+year\b", q, re.I):
            year = time.gmtime().tm_year
    language = None
    for value in ("Kannada", "Telugu", "Tamil", "Malayalam", "Hindi", "English", "Bengali", "Marathi"):
        if re.search(rf"\b{value}\b", q, re.I):
            language = value
            break
    return year, year_range, language


def _candidate_person_phrases(query: str) -> List[str]:
    """Generate a small number of likely human-name phrases.

    This is intentionally bounded. It avoids hundreds of network requests for a
    long Telegram paragraph while still handling lower-case names such as
    "duniya vijay and priyamani movies".
    """
    tokens = re.findall(r"[\wÀ-ÿ'-]+", query or "", flags=re.UNICODE)
    stop = _DISCOVERY_WORDS | {
        "kannada", "telugu", "tamil", "malayalam", "hindi", "english", "bengali", "marathi",
        "year", "years", "movie", "movies", "film", "films", "movie", "please", "me", "give",
        "find", "show", "list", "available", "files", "file", "after", "before", "from", "to",
    }
    filtered = [t for t in tokens if t.casefold() not in stop and not t.isdigit()]
    phrases = []
    # Prefer 2-3 token phrases, then single names.
    for n in (3, 2):
        for i in range(len(filtered) - n + 1):
            phrases.append(" ".join(filtered[i:i+n]))
    phrases.extend(filtered)
    # Preserve original order and cap work.
    return list(dict.fromkeys(phrases))[:24]


def _resolve_people_sync(query: str, max_people: int = 4) -> List[Tuple[str, str]]:
    phrases = _candidate_person_phrases(query)
    found = []
    seen = set()
    # Longer phrases first. We only keep confident person entities.
    for phrase in phrases:
        result = _resolve_person_sync(phrase)
        if not result:
            continue
        qid, label = result
        if qid in seen:
            continue
        seen.add(qid)
        found.append((qid, label))
        if len(found) >= max_people:
            break
    return found


def _person_hint_from_query(query: str) -> Optional[str]:
    """Fast path for the common '[person] movies' shape."""
    q = re.sub(r"\s+", " ", query or "").strip()
    patterns = [
        r"^(.{2,80}?)\s+(?:movies?|films?|filmography)\s*$",
        r"^(?:movies?|films?|filmography)\s+(?:of|by|with)\s+(.{2,80})$",
        r"^(?:show|list|give|find)\s+(?:me\s+)?(?:all\s+)?(.{2,80}?)\s+(?:movies?|films?)\s*$",
    ]
    for pattern in patterns:
        m = re.search(pattern, q, re.I)
        if m:
            value = re.sub(r"\b(?:all|the|please)\b", " ", m.group(1), flags=re.I)
            value = re.sub(r"\s+", " ", value).strip(" ,.-")
            if value:
                return value
    return None


def _discover_sync(query: str, limit: int = MAX_RESULTS) -> List[MovieCandidate]:
    year, year_range, language = _query_constraints(query)

    # 1) Structured people search. This is the most accurate and fastest route
    # for filmography and "acted together" questions.
    person_hint = _person_hint_from_query(query)
    people: List[Tuple[str, str]] = []
    if person_hint:
        resolved = _resolve_person_sync(person_hint)
        if resolved:
            people = [resolved]
    if not people:
        people = _resolve_people_sync(query, max_people=4)

    if people:
        movies = _wikidata_films_sync(
            [qid for qid, _ in people[:4]],
            year=year,
            year_range=year_range,
            language=language,
            limit=limit,
        )
        if movies:
            return _dedupe(movies, limit)

    # A language/year-only request can be answered directly from public
    # structured movie metadata; no person or local file index is needed.
    if language or year or year_range:
        movies = _wikidata_movies_by_filters_sync(
            year=year, year_range=year_range, language=language, limit=limit
        )
        if movies:
            return _dedupe(movies, limit)

    # 2) Wikipedia public search for title/topic queries and when Wikidata has
    # incomplete cast/release metadata.
    wiki_queries = [query]
    if person_hint:
        wiki_queries.insert(0, f"{person_hint} filmography")
    for wq in wiki_queries[:2]:
        movies = _wikipedia_movie_candidates_sync(wq, limit=limit)
        if movies:
            return _dedupe(movies, limit)

    # 3) Broad web search fallback. This is deliberately after structured
    # sources so arbitrary prose remains quick for common actor queries.
    results = _duckduckgo_search_sync(query, limit=12)
    out = []
    for title, url in results:
        movie = _movie_from_search_title(title)
        if movie:
            out.append(movie)
    return _dedupe(out, limit)


def discover_person_movies(person: str, limit: int = 40) -> List[MovieCandidate]:
    """Public filmography discovery for one person; never queries Media."""
    resolved = _resolve_person_sync(person)
    if resolved:
        return _wikidata_films_sync([resolved[0]], limit=limit)
    return _dedupe(_wikipedia_movie_candidates_sync(f"{person} filmography", limit=limit), limit)


def discover_movies_from_query(query: str, limit: int = 40) -> List[MovieCandidate]:
    return _discover_sync(query, limit=limit)


def _parse_json_candidates(payload: str) -> List[MovieCandidate]:
    try:
        data = json.loads(payload)
    except Exception:
        return []
    raw = data.get("movies", []) if isinstance(data, dict) else []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        try:
            year = int(item["year"]) if item.get("year") is not None else None
        except (TypeError, ValueError):
            year = None
        out.append(MovieCandidate(title=title, year=year, source=str(item.get("source") or "public-web")))
    return _dedupe(out)


async def discover_movies_with_timeout(query: str, limit: int = 40) -> List[MovieCandidate]:
    """Async public discovery. Network work runs outside Pyrogram's event loop."""
    if not looks_like_discovery_query(query):
        return []
    try:
        # A normal request should not make the bot wait indefinitely.  The cache
        # makes repeat searches effectively immediate after the first request.
        return await asyncio.wait_for(
            asyncio.to_thread(discover_movies_from_query, query, limit),
            timeout=float(os.getenv("AI_DISCOVERY_TIMEOUT", "18")),
        )
    except Exception:
        return []


def discover_movies(query: str, limit: int = 40) -> List[MovieCandidate]:
    if not looks_like_discovery_query(query):
        return []
    return discover_movies_from_query(query, limit=limit)


__all__ = [
    "MovieCandidate", "DiscoveredMovie", "discover_movies", "discover_movies_from_query",
    "discover_movies_with_timeout", "discover_person_movies", "looks_like_discovery_query",
    "_parse_json_candidates",
]
