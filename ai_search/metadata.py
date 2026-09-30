import re
from typing import Any, Dict, Optional, Tuple
from .normalization import fold, normalize_language


def size_to_bytes(value: float, unit: str) -> int:
    unit = unit.casefold()
    factor = {
        "kb": 1024,
        "k": 1024,
        "mb": 1024 ** 2,
        "m": 1024 ** 2,
        "gb": 1024 ** 3,
        "g": 1024 ** 3,
        "tb": 1024 ** 4,
        "b": 1,
    }.get(unit, 1)
    return int(value * factor)


def parse_size(text: str) -> Optional[Tuple[float, int]]:
    match = re.search(r"(?<!\w)(\d+(?:\.\d+)?)\s*(tb|gb|mb|kb|g|m|k|b)\b", text or "", re.I)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    mb = value * (1024 if unit.casefold() in {"g", "gb"} else 1)
    if unit.casefold() in {"tb"}:
        mb = value * 1024 * 1024
    elif unit.casefold() in {"kb", "k"}:
        mb = value / 1024
    elif unit.casefold() == "b":
        mb = value / (1024 ** 2)
    return mb, size_to_bytes(value, unit)


def resolution_to_quality(width: int, height: int) -> Optional[str]:
    if not width or not height:
        return None
    if height >= 2000 or width >= 3500:
        return "2160p"
    if height >= 1000 or width >= 1800:
        return "1080p"
    if height >= 650 or width >= 1100:
        return "720p"
    if height >= 430 or width >= 800:
        return "480p"
    if height >= 300 or width >= 600:
        return "360p"
    return None


def normalize_quality(value: str) -> Optional[str]:
    value = fold(value)
    if value in {"4k", "uhd", "2160", "2160p"}:
        return "2160p"
    if value in {"full hd", "fhd", "1080", "1080p"}:
        return "1080p"
    if value in {"hd", "720", "720p"}:
        return "720p"
    if value in {"480", "480p"}:
        return "480p"
    if value in {"360", "360p"}:
        return "360p"
    return None


def extract_resolution(text: str) -> Optional[Tuple[int, int]]:
    match = re.search(r"(?<!\d)(\d{3,5})\s*[x×]\s*(\d{3,5})(?!\d)", text or "", re.I)
    return (int(match.group(1)), int(match.group(2))) if match else None


def extract_season_episode(text: str):
    match = re.search(
        r"\bS(?:eason)?\s*0*(\d+)(?:\s*[-x]\s*|\s*)(?:E(?:pisode|p)?\s*0*(\d+))?\b",
        text or "",
        re.I,
    )
    if match:
        return int(match.group(1)), int(match.group(2)) if match.group(2) else None
    match = re.search(r"\b(\d+)\s*x\s*(\d+)\b", text or "", re.I)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def extract_episode(text: str) -> Optional[int]:
    match = re.search(r"\b(?:e|ep|episode)\s*0*(\d+)\b", text or "", re.I)
    return int(match.group(1)) if match else None


def extract_year(text: str) -> Optional[int]:
    match = re.search(r"\b(?:19|20)\d{2}\b", text or "")
    return int(match.group(0)) if match else None


def normalize_media_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize optional provider metadata without assuming a specific DB schema."""
    data = dict(metadata or {})
    name = str(data.get("file_name") or data.get("title") or "")

    language = data.get("language") or data.get("lang")
    if language:
        data["language"] = normalize_language(str(language)) or language
    else:
        folded = fold(name)
        for alias in ("kannada", "ಕನ್ನಡ", "hindi", "tamil", "telugu", "malayalam", "english"):
            if alias in folded:
                data["language"] = normalize_language(alias)
                break

    if not data.get("quality"):
        for token in re.findall(r"\b(?:4k|uhd|fhd|hd|1080p?|720p?|576p?|480p?|360p?)\b", name, re.I):
            quality = normalize_quality(token)
            if quality:
                data["quality"] = quality
                break

    if not data.get("resolution"):
        if data.get("width") and data.get("height"):
            data["resolution"] = (int(data["width"]), int(data["height"]))
        else:
            data["resolution"] = extract_resolution(name)

    if not data.get("quality") and data.get("resolution"):
        width, height = data["resolution"]
        data["quality"] = resolution_to_quality(width, height)

    if not data.get("season") or not data.get("episode"):
        season, episode = extract_season_episode(name)
        data.setdefault("season", season)
        data.setdefault("episode", episode)

    data.setdefault("year", extract_year(name))
    data.setdefault("themes", [])
    return data
