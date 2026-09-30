"""
Filmography helpers for AI search.

This module maps people/actors to known movie titles and provides
lightweight filename matching. It is intentionally dependency-free.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# Keep this data focused on names that the AI search needs.
# More people/titles can be added later without changing the search engine.
FILMOGRAPHY: Dict[str, List[Tuple[str, int]]] = {
    "Darshan": [
        ("Majestic", 2002),
        ("Dhruva", 2002),
        ("Kariya", 2003),
        ("Annavru", 2003),
        ("Laali Haadu", 2003),
        ("Kalavida", 2003),
        ("Namma Preethiya Ramu", 2003),
        ("Daasa", 2003),
        ("Shastri", 2005),
        ("Suntaragaali", 2006),
        ("Anatharu", 2007),
        ("Ee Bandhana", 2007),
        ("Gaja", 2008),
        ("Indra", 2008),
        ("Navagraha", 2008),
        ("Arjun", 2008),
        ("Abhay", 2009),
        ("Boss", 2011),
        ("Saarathi", 2011),
        ("Chingari", 2012),
        ("Bulbul", 2013),
        ("Brindavana", 2013),
        ("Ambareesha", 2014),
        ("Mr. Airavata", 2015),
        ("Viraat", 2016),
        ("Jaggu Dada", 2016),
        ("Chakravarthy", 2017),
        ("Taarak", 2017),
        ("Yajamana", 2019),
        ("Odeya", 2019),
        ("Roberrt", 2021),
        ("Kranti", 2023),
        ("Kaatera", 2023),
        ("Devil", 2025),
        ("Krantiveera Sangolli Rayanna", 2012),
    ],
}


# Common aliases/variations used in Telegram searches.
PERSON_ALIASES: Dict[str, str] = {
    "darshan": "Darshan",
    "challenging star darshan": "Darshan",
    "challengingstar darshan": "Darshan",
    "dboss": "Darshan",
    "d boss": "Darshan",
    "d-boss": "Darshan",
    "dharshan": "Darshan",
    "darshan thoogudeepa": "Darshan",
    "darshan thoogudeepa": "Darshan",
}


def normalize_person(person: Optional[str]) -> Optional[str]:
    """
    Normalize a person name to the canonical filmography key.
    """
    if not person:
        return None

    value = re.sub(r"\s+", " ", str(person).strip().lower())

    if value in PERSON_ALIASES:
        return PERSON_ALIASES[value]

    for alias, canonical in PERSON_ALIASES.items():
        if value == alias:
            return canonical

    # Case-insensitive canonical-name lookup.
    for canonical in FILMOGRAPHY:
        if value == canonical.lower():
            return canonical

    return person.strip()


def titles_for_person(
    person: Optional[str],
) -> List[Tuple[str, int]]:
    """
    Return known (title, year) pairs for a person.

    Results are returned chronologically.
    """
    canonical = normalize_person(person)

    if not canonical:
        return []

    titles = FILMOGRAPHY.get(canonical, [])

    # Remove accidental duplicates while preserving useful data.
    unique = {}
    for title, year in titles:
        key = (title.casefold(), year)
        unique[key] = (title, year)

    return sorted(
        unique.values(),
        key=lambda item: (item[1], item[0].casefold()),
    )


def _normalize_title(value: str) -> str:
    """
    Normalize a title for fuzzy filename matching.
    """
    value = value.lower()

    # Replace punctuation/separators with spaces.
    value = re.sub(r"[_\-.]+", " ", value)

    # Remove common technical/media tokens.
    value = re.sub(
        r"\b(?:"
        r"\d{3,4}p|"
        r"4k|2160p|1080p|720p|576p|480p|360p|"
        r"hdrip|webrip|web dl|web-dl|web|"
        r"bluray|blu ray|brrip|dvdrip|hdtv|"
        r"x264|x265|h264|h265|hevc|"
        r"proper|repack|uncut|"
        r"dual audio|dual|audio|"
        r"kannada|kannad|"
        r"english|hindi|tamil|telugu|malayalam|"
        r"mkv|mp4|avi"
        r")\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(r"\s+", " ", value).strip()

    return value


def _title_matches(filename: str, title: str) -> bool:
    """
    Check whether a known movie title occurs in a filename.
    """
    filename_norm = _normalize_title(filename)
    title_norm = _normalize_title(title)

    if not filename_norm or not title_norm:
        return False

    # Exact normalized phrase.
    if title_norm in filename_norm:
        return True

    # Token-based fallback for punctuation differences.
    title_tokens = title_norm.split()
    filename_tokens = filename_norm.split()

    if not title_tokens:
        return False

    if len(title_tokens) > len(filename_tokens):
        return False

    for index in range(len(filename_tokens) - len(title_tokens) + 1):
        if filename_tokens[index:index + len(title_tokens)] == title_tokens:
            return True

    return False


def _extract_year(filename: str) -> Optional[int]:
    """
    Extract a plausible release year from a filename.
    """
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", filename)

    for value in years:
        year = int(value)
        if 1900 <= year <= 2100:
            return year

    return None


def match_person_title(
    filename: str,
    person: Optional[str],
) -> Tuple[Optional[str], Optional[int]]:
    """
    Match a filename against the known filmography of a person.

    Returns:
        (title, year)

    Example:
        match_person_title(
            "Yajamana 2019 Kannada 720p HDRip.mkv",
            "Darshan"
        )

        -> ("Yajamana", 2019)
    """
    if not filename or not person:
        return None, None

    titles = titles_for_person(person)

    if not titles:
        return None, None

    filename_year = _extract_year(filename)

    # Prefer a title whose filename year matches its known release year.
    if filename_year is not None:
        for title, year in titles:
            if year == filename_year and _title_matches(filename, title):
                return title, year

    # Fall back to title-only matching.
    for title, year in titles:
        if _title_matches(filename, title):
            return title, filename_year or year

    return None, None


def person_known_title(
    filename: str,
    person: Optional[str],
) -> bool:
    """
    Convenience helper used by search/ranking code.
    """
    title, _ = match_person_title(filename, person)
    return title is not None



# ---------------------------------------------------------------------------
# Optional dynamic filmography lookup
# ---------------------------------------------------------------------------
# The local filmography above is deliberately dependency-free.  For people
# not present there, AI search can ask Wikidata for a public filmography.
# This is best-effort and cached in memory; MongoDB remains the source of files.
import asyncio
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_REMOTE_CACHE: Dict[str, Tuple[float, List[Tuple[str, int]]]] = {}
_REMOTE_TTL = 6 * 60 * 60


def _wikidata_json(url: str, params: Dict[str, str], timeout: float = 6.0):
    query = urlencode(params)
    req = Request(
        f"{url}?{query}",
        headers={"User-Agent": "akfilter-ai-search/1.0 (movie search bot)"}
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _remote_person_titles_sync(person: str) -> List[Tuple[str, int]]:
    canonical = normalize_person(person) or person.strip()
    key = canonical.casefold()
    cached = _REMOTE_CACHE.get(key)
    if cached and time.time() - cached[0] < _REMOTE_TTL:
        return list(cached[1])

    # Resolve a human entity by name.
    search = _wikidata_json(
        "https://www.wikidata.org/w/api.php",
        {
            "action": "wbsearchentities", "search": canonical,
            "language": "en", "format": "json", "limit": "5",
        },
    )
    candidates = search.get("search", [])
    qid = None
    for item in candidates:
        if item.get("id", "").startswith("Q"):
            desc = (item.get("description") or "").lower()
            label = (item.get("label") or "").casefold()
            if "actor" in desc or "actress" in desc or "film" in desc or label == key:
                qid = item["id"]
                break
    if not qid and candidates:
        qid = candidates[0].get("id")
    if not qid:
        return []

    # Reverse cast-member relation: films where this person is P161.
    sparql = (
        "SELECT ?film ?filmLabel ?date WHERE { "
        f"?film wdt:P161 wd:{qid}. "
        "OPTIONAL { ?film wdt:P577 ?date. } "
        "SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". } "
        "} ORDER BY DESC(?date) LIMIT 500"
    )
    data = _wikidata_json(
        "https://query.wikidata.org/sparql",
        {"query": sparql, "format": "json"},
        timeout=10.0,
    )
    values = data.get("results", {}).get("bindings", [])
    found = {}
    for row in values:
        title = row.get("filmLabel", {}).get("value")
        date = row.get("date", {}).get("value", "")
        if not title:
            continue
        match = re.search(r"(19|20)\d{2}", date)
        year = int(match.group(0)) if match else 0
        found[(title.casefold(), year)] = (title, year)
    result = sorted(found.values(), key=lambda x: (x[1] or 9999, x[0].casefold()), reverse=True)
    _REMOTE_CACHE[key] = (time.time(), result)
    return result


async def titles_for_person_async(person: Optional[str]) -> List[Tuple[str, int]]:
    """Return local filmography first, then best-effort public Wikidata data."""
    local = titles_for_person(person)
    if local:
        return local
    if not person:
        return []
    try:
        return await asyncio.to_thread(_remote_person_titles_sync, person)
    except Exception:
        return []

__all__ = [
    "FILMOGRAPHY",
    "PERSON_ALIASES",
    "normalize_person",
    "titles_for_person",
    "titles_for_person_async",
    "match_person_title",
    "person_known_title",
]
