import re
from typing import Iterable, Optional
from .models import SearchIntent
from .normalization import LANGUAGE_ALIASES, correct_token, fold, normalize_language, normalize_title, parse_number_word
from .metadata import extract_episode, extract_resolution, extract_season_episode, normalize_quality, parse_size

class QueryParser:
    """Deterministic multilingual baseline parser; an AI provider can enrich it later."""
    def __init__(self, known_entities: Optional[Iterable[str]] = None):
        self.known_entities = list(known_entities or ["Darshan", "Kantara", "KGF"])
        self.vocabulary = self.known_entities + list(LANGUAGE_ALIASES) + ["movie", "movies", "movi", "series", "film", "cinema"]

    def parse(self, query: str) -> SearchIntent:
        original = query or ""
        text = fold(original)
        intent = SearchIntent(original_query=original, normalized_query=text)
        for token in re.findall(r"[^\s]+", text):
            correction = correct_token(token, self.vocabulary)
            if correction and correction.casefold() != token.casefold():
                intent.corrections.append((token, correction))
        corrected = text
        for old, new in intent.corrections: corrected = re.sub(rf"\b{re.escape(old)}\b", new, corrected, flags=re.I)
        intent.normalized_query = corrected
        for alias, language in LANGUAGE_ALIASES.items():
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", corrected, re.I):
                intent.language = language; intent.known["language"] = language; break
        year_range = re.search(r"\b(19\d{2}|20\d{2})\s*(?:-|to|–)\s*(19\d{2}|20\d{2})\b", corrected)
        if year_range: intent.year_range = (int(year_range.group(1)), int(year_range.group(2)))
        else:
            years = re.findall(r"\b(?:19|20)\d{2}\b", corrected)
            if years: intent.year = int(years[0])
        size = parse_size(corrected)
        if size: intent.target_size_mb = size[0]
        intent.resolution = extract_resolution(corrected)
        quality = next((normalize_quality(x) for x in re.findall(r"\b(?:4k|uhd|fhd|hd|full\s+hd|\d{3,4}p?)\b", corrected, re.I) if normalize_quality(x)), None)
        intent.quality = quality
        intent.season, intent.episode = extract_season_episode(corrected)
        if intent.episode is None: intent.episode = extract_episode(corrected)
        if re.search(r"\b(series|show|web\s*series|ಸರಣಿ)\b", corrected, re.I): intent.content_type = "series"
        elif re.search(r"\b(movie|movies|film|cinema|ಚಿತ್ರ|ಸಿನಿಮ���)\b", corrected, re.I): intent.content_type = "movie"
        if re.search(r"\b(small|smallest|low\s*size)\b", corrected): intent.sort_order = "smallest"
        elif re.search(r"\b(large|largest|big|high\s*size)\b", corrected): intent.sort_order = "largest"
        elif re.search(r"\brandom\b", corrected): intent.sort_order = "random"
        if re.search(r"\b(latest|new)\b", corrected): intent.sort_order = "year"
        themes = {"romantic": "romance", "love": "romance", "action": "action", "revenge": "revenge", "friendship": "friendship", "family": "family", "sentiment": "sentiment", "brother": "brotherhood", "anna thamma": "brotherhood"}
        intent.themes = [value for key, value in themes.items() if key in corrected]
        reserved = set(LANGUAGE_ALIASES) | {"movie", "movies", "film", "films", "cinema", "ಚಿತ್ರ", "ಸಿನಿಮಾ", "series", "show", "season", "episode", "around", "from", "latest", "and", "avara", "ಅವರ"}
        entities = []
        for entity in self.known_entities:
            if fold(entity) in corrected or any(fold(entity) == fold(new) for _, new in intent.corrections): entities.append(entity)
        if entities:
            intent.person = entities[0] if entities[0].casefold() == "darshan" else None
            if intent.person: intent.person_type = "person"
            else: intent.title = entities[0]
        elif not intent.language and not intent.year and not intent.quality and len(corrected.split()) <= 4:
            candidate = normalize_title(" ".join(x for x in corrected.split() if x not in reserved))
            if candidate: intent.title = candidate
        intent.keywords = [x for x in corrected.split() if x not in reserved and not x.isdigit()]
        intent.inferred["content_type"] = intent.content_type or ("movie" if intent.person else None)
        intent.confidence = min(1.0, .35 + .1 * len(intent.known) + .1 * bool(intent.person or intent.title) + .1 * bool(intent.language))
        return intent
