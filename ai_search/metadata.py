import re
from typing import Optional, Tuple
from .normalization import fold


def size_to_bytes(value: float, unit: str) -> int:
    unit = unit.casefold()
    factor = {"kb": 1024, "k": 1024, "mb": 1024**2, "m": 1024**2,
              "gb": 1024**3, "g": 1024**3, "tb": 1024**4, "b": 1}.get(unit, 1)
    return int(value * factor)


def parse_size(text: str) -> Optional[Tuple[float, int]]:
    match = re.search(r"(?<!\w)(\d+(?:\.\d+)?)\s*(tb|gb|mb|kb|tb|g|m|k|b)\b", text, re.I)
    if not match:
        return None
    value = float(match.group(1))
    return value * (1024 if match.group(2).casefold() in {"g", "gb"} else 1), size_to_bytes(value, match.group(2))


def resolution_to_quality(width: int, height: int) -> Optional[str]:
    if not width or not height:
        return None
    if height >= 2000 or width >= 3500: return "2160p"
    if height >= 1000 or width >= 1800: return "1080p"
    if height >= 650 or width >= 1100: return "720p"
    if height >= 430 or width >= 800: return "480p"
    if height >= 300 or width >= 600: return "360p"
    return None


def normalize_quality(value: str) -> Optional[str]:
    value = fold(value)
    if value in {"4k", "uhd", "2160", "2160p"}: return "2160p"
    if value in {"full hd", "fhd", "1080", "1080p"}: return "1080p"
    if value in {"hd", "720", "720p"}: return "720p"
    if value in {"480", "480p"}: return "480p"
    if value in {"360", "360p"}: return "360p"
    return None


def extract_resolution(text: str) -> Optional[Tuple[int, int]]:
    match = re.search(r"(?<!\d)(\d{3,5})\s*[x×]\s*(\d{3,5})(?!\d)", text, re.I)
    return (int(match.group(1)), int(match.group(2))) if match else None


def extract_season_episode(text: str):
    match = re.search(r"\bS(?:eason)?\s*0*(\d+)(?:\s*[-x]\s*|\s*)(?:E(?:pisode|p)?\s*0*(\d+))?\b", text, re.I)
    if match:
        return int(match.group(1)), int(match.group(2)) if match.group(2) else None
    match = re.search(r"\b(\d+)\s*x\s*(\d+)\b", text, re.I)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def extract_episode(text: str) -> Optional[int]:
    match = re.search(r"\b(?:e|ep|episode)\s*0*(\d+)\b", text, re.I)
    return int(match.group(1)) if match else None
