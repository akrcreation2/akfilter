# Free External Movie Discovery

This discovery stage does not require an OpenAI/Gemini/Groq API key.

## Search flow

1. The Telegram message is treated as a natural-language discovery request when it is not a technical file query.
2. Public external sources are searched first — Wikidata structured data, Wikipedia search, and DuckDuckGo web search.
3. For people queries, Wikidata is used to resolve the person and retrieve films through the public `cast member (P161)` and release-date relationships. For multiple people, the query requires the movie to contain all resolved people, which supports "acted together" searches.
4. Year/language constraints are applied to public metadata where available.
5. The bot shows discovered movie title/year buttons.
6. Only after a user clicks a movie button does the existing Media/file database run.
7. If public discovery returns nothing, the existing file search is used as a compatibility fallback.

## Speed

Responses are cached under `AI_DISCOVERY_CACHE_DIR` (default `ai_search/cache`). Repeat queries therefore avoid the external network. Network work runs in a worker thread so it does not block Pyrogram.

## Optional environment variables

- `AI_DISCOVERY_CACHE_DIR`
- `AI_DISCOVERY_CACHE_TTL` (default `604800`)
- `AI_DISCOVERY_NETWORK_TIMEOUT` (default `8`)
- `AI_DISCOVERY_TIMEOUT` (default `18`)

No AI API key is required for this discovery implementation.
