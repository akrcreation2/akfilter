import re
import unicodedata
from difflib import get_close_matches
from typing import Iterable, Optional

LANGUAGE_ALIASES = {
    "kannada": "Kannada", "kannad": "Kannada", "ಕನ್ನಡ": "Kannada", "ಕನ್ನಡದ": "Kannada",
    "kan": "Kannada", "english": "English", "hindi": "Hindi", "हिंदी": "Hindi",
    "tamil": "Tamil", "தமிழ்": "Tamil", "telugu": "Telugu", "తెలుగు": "Telugu",
    "malayalam": "Malayalam", "മലയാളം": "Malayalam", "marathi": "Marathi", "मराठी": "Marathi",
    "bengali": "Bengali", "বাংলা": "Bengali", "punjabi": "Punjabi", "ਪੰਜਾਬੀ": "Punjabi",
    "gujarati": "Gujarati", "ગુજરાતી": "Gujarati", "urdu": "Urdu", "اردو": "Urdu",
}
LANGUAGE_WORDS = set(LANGUAGE_ALIASES)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"[^\w\u0900-\u097f\u0c80-\u0cff\u0b80-\u0bff\u0d00-\u0d7f\u0980-\u09ff\u0a80-\u0aff\u0c00-\u0c7f]+", " ", text).strip()


def normalize_language(value: str) -> Optional[str]:
    key = fold(value)
    return LANGUAGE_ALIASES.get(key)


def normalize_title(value: str) -> str:
    value = fold(value)
    value = re.sub(r"\b(?:movie|movies|film|films|cinema|ಚಿತ್ರ|ಸಿನಿಮಾ|ಚಿತ್ರಗಳು|series|show)\b", " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip()
    return value.title() if value.isascii() else value


def correct_token(token: str, vocabulary: Iterable[str], cutoff: float = .82) -> Optional[str]:
    matches = get_close_matches(token.casefold(), [x.casefold() for x in vocabulary], n=1, cutoff=cutoff)
    if not matches:
        return None
    wanted = matches[0]
    return next((x for x in vocabulary if x.casefold() == wanted), wanted)


def parse_number_word(value: str) -> Optional[int]:
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    return words.get(fold(value))
