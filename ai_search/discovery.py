"""AI-first movie discovery.

Discovery is deliberately separate from the bot's Media/file database:
- this module finds movie titles/years from public web/AI metadata;
- the existing Media database is consulted only after the user clicks a title.

The preferred provider is OpenAI Responses + web search when OPENAI_API_KEY is
configured. A lightweight Wikipedia/Google fallback keeps the feature useful
when no AI key is configured.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class MovieCandidate:
    title: str
    year: Optional[int] = None
    reason: Optional[str] = None


_DISCOVERY_CACHE: Dict[str, tuple[float, List[MovieCandidate]]] = {}
_CACHE_TTL = 900


def _cache_get(key: str) -> Optional[List[MovieCandidate]]:
    item = _DISCOVERY_CACHE.get(key)
    if not item:
        return None
    if time.time() - item[0] > _CACHE_TTL:
        _DISCOVERY_CACHE.pop(key, None)
        return None
    return list(item[1])


def _cache_put(key: str, value: List[MovieCandidate]) -> None:
    if len(_DISCOVERY_CACHE) > 256:
        oldest = min(_DISCOVERY_CACHE.items(), key=lambda x: x[1][0])[0]
        _DISCOVERY_CACHE.pop(oldest, None)
    _DISCOVERY_CACHE[key] = (time.time(), list(value))


def _clean_title(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"\s+", " ", value).strip(" -–—|•\t\n")
    value = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", value)
    return value.strip()


def _valid_year(year: Any) -> Optional[int]:
    try:
        value = int(year)
        return value if 1880 <= value <= 2100 else None
    except Exception:
        return None


def _parse_json_candidates(text: str) -> List[MovieCandidate]:
    if not text:
        return []
    text = text.strip()
    # Accept fenced JSON and a JSON object containing movies.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    candidates: Any = None
    try:
        candidates = json.loads(text)
    except Exception:
        match = re.search(r"(\[\s*\{.*\}\s*\])", text, re.S)
        if match:
            try:
                candidates = json.loads(match.group(1))
            except Exception:
                pass
    if isinstance(candidates, dict):
        candidates = candidates.get("movies") or candidates.get("results") or []
    if not isinstance(candidates, list):
        return []
    out: List[MovieCandidate] = []
    seen = set()
    for item in candidates:
        if isinstance(item, str):
            title, year = item, None
            reason = None
        elif isinstance(item, dict):
            title = item.get("title") or item.get("name")
            year = item.get("year") or item.get("release_year")
            reason = item.get("reason")
        else:
            continue
        title = _clean_title(title)
        if not title or len(title) > 160:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(MovieCandidate(title=title, year=_valid_year(year), reason=reason))
    return out[:100]


def _response_text(payload: Dict[str, Any]) -> str:
    # Responses API may expose output_text directly or text blocks in output.
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: List[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks)


async def _openai_discover(query: str) -> List[MovieCandidate]:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AI_SEARCH_API_KEY")
    if not api_key:
        return []

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = f"""You are the movie-discovery layer of a Telegram bot.
Interpret the user's request literally and use web search to identify MOVIES.
Do not search the bot's file/database. The result is only a public metadata list.

User request:
{query}

Rules:
- If a person/actor/actress is named, return their relevant movie filmography.
- If two or more people are named, return movies where the requested people are both involved, when that is what the request asks.
- If a song is named, identify the movie containing that song when possible.
- Respect language, year/year-range, relationship, and other constraints.
- For a generic movie-list request, return movie titles and release years.
- Do not invent titles. Prefer authoritative sources and cross-check when practical.
- Return ONLY JSON: {{"movies":[{{"title":"...","year":2021,"reason":"..."}}]}}.
- Maximum 100 movies. No commentary outside JSON."""

    body = {
        "model": model,
        "input": prompt,
        "tools": [{"type": "web_search_preview"}],
        "temperature": 0,
    }
    timeout = aiohttp.ClientTimeout(total=float(os.getenv("AI_SEARCH_TIMEOUT", "35")))
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            ) as response:
                if response.status >= 400:
                    logger.warning("AI discovery provider returned HTTP %s", response.status)
                    return []
                payload = await response.json()
        return _parse_json_candidates(_response_text(payload))
    except Exception:
        logger.exception("AI web discovery failed")
        return []


async def _wikipedia_search(query: str) -> List[MovieCandidate]:
    """Fallback for person/filmography discovery without an AI key."""
    # Search Wikipedia for the whole request first; then try likely person terms.
    api = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "utf8": 1, "srlimit": 8,
    }
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "AKFilter-AISearch/1.0"}) as session:
            async with session.get(api, params=params) as response:
                if response.status >= 400:
                    return []
                data = await response.json()
        titles = [x.get("title", "") for x in data.get("query", {}).get("search", [])]
        results: List[MovieCandidate] = []
        for title in titles:
            if re.search(r"\b(19|20)\d{2}\b", title):
                year_match = re.search(r"\b((?:19|20)\d{2})\b", title)
                results.append(MovieCandidate(_clean_title(title), _valid_year(year_match.group(1)) if year_match else None))
        return results[:30]
    except Exception:
        return []


async def _google_search_fallback(query: str) -> List[MovieCandidate]:
    """Best-effort public Google result fallback; never touches the Media DB."""
    url = "https://www.google.com/search?q=" + quote_plus(query + " movie filmography")
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}) as session:
            async with session.get(url) as response:
                if response.status >= 400:
                    return []
                body = await response.text(errors="ignore")
        soup = BeautifulSoup(body, "html.parser")
        out: List[MovieCandidate] = []
        seen = set()
        for heading in soup.select("h3"):
            title = _clean_title(heading.get_text(" ", strip=True))
            if not title or len(title) > 120:
                continue
            parent = heading.parent
            snippet = parent.get_text(" ", strip=True) if parent else ""
            year_match = re.search(r"\b((?:19|20)\d{2})\b", snippet)
            key = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
            if key and key not in seen:
                seen.add(key)
                out.append(MovieCandidate(title, _valid_year(year_match.group(1)) if year_match else None))
        return out[:30]
    except Exception:
        return []


async def discover_movies(query: str) -> List[MovieCandidate]:
    key = re.sub(r"\s+", " ", (query or "").strip().casefold())
    if not key:
        return []
    cached = _cache_get(key)
    if cached is not None:
        return cached

    # AI web discovery is the primary path. Fallbacks are public metadata only.
    results = await _openai_discover(query)
    if not results:
        results = await _wikipedia_search(query)
    if not results:
        results = await _google_search_fallback(query)

    _cache_put(key, results)
    return results


async def discover_movies_with_timeout(query: str) -> List[MovieCandidate]:
    try:
        return await asyncio.wait_for(discover_movies(query), timeout=40)
    except asyncio.TimeoutError:
        logger.warning("Movie discovery timed out")
        return []


def looks_like_discovery_query(query: str) -> bool:
    """Return True when the message is asking AI to discover titles, not files."""
    text = re.sub(r"\s+", " ", (query or "").strip().casefold())
    if not text:
        return False
    # Explicit file-search constraints should stay on the proven legacy path.
    if re.search(r"\b(?:\d{3,4}p|4k|2160p|1080p|720p|480p|360p|mkv|mp4|file|files|download|size|s\s*\d+|e\s*\d+)\b", text):
        return False
    if len(text) > 160:
        return True
    discovery_words = (
        "movie", "movies", "film", "films", "filmography", "acted", "acting",
        "actor", "actress", "hero", "heroine", "starring", "cast", "song", "songs",
        "this year", "last year", "current year", "all movies", "list movies",
        "movies of", "movies with", "acted together", "worked together",
        "ಚಿತ್ರ", "ಸಿನಿಮಾ", "ಹಾಡು", "ನಟ", "ನಟಿ",
    )
    if any(word in text for word in discovery_words):
        return True
    # A short name-like query is also useful as a movie/person discovery request.
    if 2 <= len(text.split()) <= 5 and not re.search(r"[!?@#$%^*]", text):
        return True
    return False
