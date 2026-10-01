# AI Search

The project has two intentionally separate search stages.

## Stage 1 — external movie discovery

`ai_search.discovery` is discovery-first for normal movie/person/natural-language queries. It does **not** query the bot's MongoDB `Media` collection. It uses public external sources without a paid AI API key:

- Wikidata entity search and SPARQL for structured cast/release/language relationships.
- Wikipedia search for public movie pages and filmography information.
- DuckDuckGo HTML search as a broad web-search fallback.

This supports queries such as actor filmographies, multiple people who acted together, language/year movie requests, dubbed/movie-topic searches, and long natural-language requests when the public sources can answer them.

The results are normalized into `MovieCandidate(title, year, source)` and shown as Telegram buttons.

## Stage 2 — existing file search

The bot's Media/file database is queried only after the user clicks one of the discovered movie buttons. The existing file buttons, captions, pagination and Get File flow are preserved. If external discovery produces no usable result, the existing search path is used as a fallback.

## Caching and speed

Discovery results are cached under `AI_DISCOVERY_CACHE_DIR` (default `ai_search/cache`). Network requests run outside the Pyrogram event loop and have bounded timeouts.

No OpenAI, Gemini, Groq, or other paid AI API key is required.
