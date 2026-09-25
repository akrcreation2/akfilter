# Isolated AI search subsystem

## Scope

`ai_search` is a dependency-light, deterministic baseline for parsing and ranking
natural-language movie/series requests. It does not import or alter the Telegram
handlers, `database/ia_filterdb.py`, MongoDB schema, or existing filter flow.

## Extension points

- Implement `MetadataProvider` for title/person metadata or an AI-backed resolver.
- Implement `SearchProvider` as an adapter over a new indexed collection or a
  read-only projection of the existing media collection.
- Call `SearchEngine.search(intent)` from a future opt-in handler. Keep the
  current filter as fallback whenever the adapter returns no confident results.

The parser intentionally does not fabricate metadata. Unknown entities remain
keywords and can be resolved by a provider later. Quality extraction from actual
video streams is also adapter-owned: `normalize_media_metadata` accepts width,
height, codec, bitrate, and duration supplied by a one-time indexing process.

Example:

```python
from ai_search import QueryParser
intent = QueryParser().parse("ದರ್ಶನ್ ಕನ್ನಡ ಚಿತ್ರ 400MB 1080p")
```

No API keys are read or logged by this package.
