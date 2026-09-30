import re
from datetime import datetime, timezone
from typing import Iterable, Optional
from .models import SearchIntent
from .normalization import LANGUAGE_ALIASES, correct_token, fold, normalize_title
from .metadata import extract_episode, extract_resolution, extract_season_episode, normalize_quality, parse_size
from .filmography import normalize_person, titles_for_person


class QueryParser:
    """Multilingual, natural-language movie/file intent parser.

    It is deliberately local and deterministic.  It extracts the useful search
    constraints from short Telegram queries as well as long natural-language
    requests; the database remains the final source of available files.
    """

    DEFAULT_ENTITIES = {
        "darshan": "Darshan", "ದರ್ಶನ್": "Darshan",
        "dharshan": "Darshan", "dboss": "Darshan", "d boss": "Darshan",
        "challenging star": "Darshan", "challenging star darshan": "Darshan",
        "kantara": "Kantara", "kgf": "KGF",
    }

    def __init__(self, known_entities: Optional[Iterable[str]] = None):
        supplied = list(known_entities or [])
        self.entity_aliases = dict(self.DEFAULT_ENTITIES)
        self.entity_aliases.update({fold(value): value for value in supplied})
        self.known_entities = list(dict.fromkeys(self.entity_aliases.values()))
        self.vocabulary = (
            self.known_entities + list(self.entity_aliases) +
            list(LANGUAGE_ALIASES) +
            ["movie", "movies", "movi", "film", "films", "cinema",
             "series", "show", "acted", "actor", "actress", "hero",
             "heroine", "cast", "star", "filmography", "year", "language",
             "quality", "file", "files", "download", "available"]
        )

    def _extract_people(self, corrected: str, intent: SearchIntent):
        people = []
        # Known local person aliases win over generic extraction.  Known movie
        # titles such as Kantara/KGF must remain titles unless the surrounding
        # sentence explicitly says they are a person.
        explicit_person_signal = bool(re.search(
            r"\b(?:acted\s+by|starring|featuring|filmography|actor|actress|hero|heroine)\b",
            corrected, re.I
        ))
        for alias, entity in self.entity_aliases.items():
            if not re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", corrected, re.I):
                continue
            if entity.casefold() == "darshan" or explicit_person_signal:
                if entity.casefold() not in {x.casefold() for x in people}:
                    people.append(entity)

        # Natural language patterns: "movies acted by Yash", "Yash movies",
        # "filmography of Puneeth Rajkumar", "Yash and Radhika movies".
        patterns = [
            r"(?:movies?|films?|filmography)\s+(?:acted\s+by|of|with)\s+([A-Za-z][A-Za-z .'-]{1,60})",
            r"(?:acted\s+by|starring|featuring|cast(?:ed)?\s+by)\s+([A-Za-z][A-Za-z .'-]{1,100})",
            r"\b([A-Za-z][A-Za-z .'-]{1,50})\s+(?:movies?|films?|filmography)\b",
        ]
        stop = r"(?:\s+(?:in|from|for|year|language|quality|available)\b.*)$"
        for pattern in patterns:
            for match in re.finditer(pattern, corrected, re.I):
                candidate = re.sub(stop, "", match.group(1), flags=re.I).strip(" ,.-")
                # Explicit cast clauses can contain multiple people.
                candidate = re.sub(r"\b(?:please|find|show|give|me|all|the)\b", " ", candidate, flags=re.I)
                # Strip search constraints accidentally captured as part of the
                # person's name (e.g. "Darshan Kannada movies").
                for lang_alias in LANGUAGE_ALIASES:
                    candidate = re.sub(
                        rf"\b{re.escape(lang_alias)}\b", "", candidate, flags=re.I
                    )
                candidate = re.sub(
                    r"\b(?:movie|movies|film|films|cinema|ಚಿತ್ರ|ಸಿನಿಮಾ)\b",
                    "", candidate, flags=re.I
                )
                candidate = re.sub(r"\s+", " ", candidate).strip(" ,.-")
                if (not candidate or candidate.casefold() in {"all", "the", "any", "movie", "movies"}
                        or re.search(r"\b(?:please\s+find|find\s+all|show\s+me|give\s+me)\b", candidate, re.I)):
                    continue
                # A known title should remain a title, not become a person.
                if any(candidate.casefold() == x.casefold() for x in self.known_entities
                       if x.casefold() != "darshan"):
                    continue
                # "Yash and Radhika Pandit" is a combined-person query.
                pieces = re.split(r"\s+(?:and|&)\s+", candidate, flags=re.I)
                for person_piece in pieces:
                    person_piece = person_piece.strip(" ,.-")
                    if not person_piece:
                        continue
                    value = person_piece.title() if person_piece.isascii() else person_piece
                    if value.casefold() not in {x.casefold() for x in people}:
                        people.append(value)

        # Explicit "X and Y movies" / "X & Y acted movies".
        head = re.search(
            r"^(.{2,100}?)\s+(?:acted\s+)?(?:movies?|films?)\b",
            corrected, re.I
        )
        if head:
            for piece in re.split(r"\s+(?:and|&)\s+", head.group(1)):
                piece = piece.strip(" ,.-")
                for lang_alias in LANGUAGE_ALIASES:
                    piece = re.sub(rf"\b{re.escape(lang_alias)}\b", "", piece, flags=re.I)
                piece = re.sub(r"\s+", " ", piece).strip(" ,.-")
                if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,40}", piece):
                    if piece.casefold() not in {x.casefold() for x in people}:
                        if piece.casefold() not in {x.casefold() for x in self.known_entities}:
                            people.append(piece.title())

        intent.persons = people
        if people:
            intent.person = people[0]
            intent.person_type = "person"
            intent.inferred["person_query"] = True
            intent.inferred["person_count"] = len(people)

    def parse(self, query: str) -> SearchIntent:
        original = query or ""
        text = fold(original)
        intent = SearchIntent(original_query=original, normalized_query=text)

        # Correct only short/obvious typo tokens; never rewrite arbitrary long
        # prose because that can damage a title or a person's name.
        tokens = re.findall(r"[^\s]+", text)
        if len(tokens) <= 8:
            for token in tokens:
                correction = correct_token(token, self.vocabulary)
                if correction and correction.casefold() != token.casefold():
                    intent.corrections.append((token, correction))
        corrected = text
        for old, new in intent.corrections:
            corrected = re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, corrected, flags=re.I)
        intent.normalized_query = corrected

        for alias, language in LANGUAGE_ALIASES.items():
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", corrected, re.I):
                intent.language = language
                intent.known["language"] = language
                break

        # Relative-year language is common in natural Telegram requests.
        current_year = datetime.now(timezone.utc).year
        if re.search(r"\b(this|current)\s+year\b", corrected, re.I):
            intent.year = current_year
        elif re.search(r"\b(last|previous)\s+year\b", corrected, re.I):
            intent.year = current_year - 1

        year_range = re.search(r"\b(19\d{2}|20\d{2})\s*(?:-|to|–)\s*(19\d{2}|20\d{2})\b", corrected)
        if year_range:
            intent.year_range = (int(year_range.group(1)), int(year_range.group(2)))
        else:
            years = re.findall(r"\b(?:19|20)\d{2}\b", corrected)
            if years:
                intent.year = int(years[0])

        size = parse_size(corrected)
        if size:
            intent.target_size_mb = size[0]

        intent.resolution = extract_resolution(corrected)
        quality = next(
            (normalize_quality(x) for x in re.findall(
                r"\b(?:4k|uhd|fhd|hd|full\s+hd|\d{3,4}p?)\b", corrected, re.I
            ) if normalize_quality(x)), None
        )
        intent.quality = quality
        intent.season, intent.episode = extract_season_episode(corrected)
        if intent.episode is None:
            intent.episode = extract_episode(corrected)

        if re.search(r"\b(series|web\s*series|ಸರಣಿ)\b", corrected, re.I):
            intent.content_type = "series"
        elif re.search(r"\b(movie|movies|film|films|cinema|ಚಿತ್ರ|ಸಿನಿಮಾ|ಚಿತ್ರಗಳು)\b", corrected, re.I):
            intent.content_type = "movie"

        if re.search(r"\b(small|smallest|low\s*size)\b", corrected):
            intent.sort_order = "smallest"
        elif re.search(r"\b(large|largest|big|high\s*size)\b", corrected):
            intent.sort_order = "largest"
        elif re.search(r"\brandom\b", corrected):
            intent.sort_order = "random"
        elif re.search(r"\b(latest|newest|new|recent)\b", corrected):
            intent.sort_order = "year"

        themes = {
            "romantic": "romance", "love": "romance", "action": "action",
            "revenge": "revenge", "friendship": "friendship",
            "family": "family", "sentiment": "sentiment",
            "brother": "brotherhood", "anna thamma": "brotherhood",
        }
        intent.themes = [value for key, value in themes.items() if key in corrected]

        reserved = set(LANGUAGE_ALIASES) | {
            "movie", "movies", "film", "films", "cinema", "ಚಿತ್ರ", "ಸಿನಿಮಾ",
            "ಚಿತ್ರಗಳು", "series", "show", "season", "episode", "around",
            "from", "latest", "new", "newest", "recent", "this", "current", "last", "previous", "year", "and", "or",
            "avara", "ಅವರ", "acted", "acting", "actor", "actress", "hero",
            "heroine", "cast", "starring", "filmography", "find", "show",
            "give", "send", "me", "all", "available", "files", "file",
        }

        # First classify explicit person/movie entities.
        self._extract_people(corrected, intent)
        if intent.person and not intent.year and intent.sort_order == "relevance":
            # "X movies" means a filmography/list request; newest first is the
            # most useful deterministic presentation.
            intent.sort_order = "year"

        entities = []
        for alias, entity in self.entity_aliases.items():
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", corrected, re.I):
                entities.append(entity)

        # A known non-person entity is a title.
        for entity in entities:
            if entity.casefold() != "darshan" and not intent.person:
                intent.title = entity
                break

        if not intent.person and not intent.title and len(corrected.split()) <= 8:
            candidate = normalize_title(" ".join(
                x for x in corrected.split()
                if x not in reserved and not x.isdigit()
            ))
            if candidate:
                intent.title = candidate

        # For a person query, don't pass the person's name as a filename keyword.
        keywords = []
        person_tokens = set()
        for p in intent.persons:
            person_tokens.update(fold(p).split())
        for x in corrected.split():
            if x in reserved or x.isdigit() or x in person_tokens:
                continue
            if len(x) >= 2:
                keywords.append(x)
        intent.keywords = list(dict.fromkeys(keywords))

        if intent.person:
            intent.inferred["content_type"] = intent.content_type or "movie"
        else:
            intent.inferred["content_type"] = intent.content_type

        evidence = sum(bool(x) for x in (
            intent.title, intent.person, intent.language, intent.year,
            intent.quality, intent.target_size_mb, intent.season, intent.episode
        ))
        # Person extraction from natural language is strong evidence; long prose
        # itself is not treated as low confidence.
        intent.confidence = min(1.0, 0.30 + 0.10 * evidence + 0.10 * bool(intent.persons))
        if intent.title and titles_for_person(intent.title):
            intent.person = intent.title
            intent.persons = [intent.title]
            intent.title = None
            intent.person_type = "person"
            intent.confidence = min(1.0, intent.confidence + 0.2)
        return intent
