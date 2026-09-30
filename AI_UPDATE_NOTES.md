# AI Search Integration Update

This ZIP is based on the uploaded `akfilter-ai-search-phase-1` project.

## Modified files

1. `ai_search/README.md`
   - Updated production behavior documentation.

2. `ai_search/adapter.py`
   - Connects the AI search engine to the existing MongoDB `Media` collection.
   - Converts database documents into AI `SearchResult` objects for ranking.
   - Keeps the original Media document attached so the existing Telegram UI can receive the exact original file object.
   - Adds filename metadata extraction for language, year, quality, resolution, season and episode.
   - Applies explicit query filters while preserving broad candidate matching.

3. `ai_search/integration.py`
   - Makes AI search a drop-in replacement for the existing `get_search_results()` contract.
   - AI-first search for understood queries.
   - Automatic fallback to the original database search if AI parsing/search fails or produces no usable result.
   - Preserves `(files, next_offset, total_results)` pagination behavior.
   - Returns original Media documents, not AI wrapper objects.

4. `ai_search/metadata.py`
   - Added robust media metadata normalization.
   - Added year extraction and resolution-to-quality handling.
   - Fixed metadata support used by ranking.
   - Improved file-size parsing.

5. `plugins/pm_filter.py`
   - Existing PM search flow now calls `ai_aware_search()`.
   - Existing buttons, captions, IMDb display, spell-check UI, pagination and file sending logic remain in place.
   - AI search is also used when moving through the normal PM search pagination and spell-selection flow.

## Unmodified

All other original project files were kept unchanged.

## Validation

- 25 AI-search unit/integration tests passed.
- Python compilation of the modified AI-search and PM-filter modules passed.

## Runtime requirement

No external AI API key is required by this implementation. It is a deterministic local query-understanding/ranking layer using the existing MongoDB data.


### Phase 1.1 person-query fix

6. `ai_search/filmography.py`
   - Adds local title/year hints for Darshan filmography.
   - Expands person queries into existing movie titles without changing the Media schema or requiring an external API.

7. `ai_search/parser.py`
   - Adds common Darshan aliases such as `D Boss`, `DBoss`, `Challenging Star`, and Kannada `ದರ್ಶನ್` handling.
   - Uses newest-first year sorting for actor movie-list queries.

8. `ai_search/adapter.py`
   - Expands actor queries to known film titles before querying the existing MongoDB collection.
   - Preserves the original Media documents and Telegram result flow.
   - Applies year/language/quality/season/episode filters to expanded results.

9. `tests/ai_search/test_filmography.py`
   - Adds regression coverage for actor title expansion, year inference, and the existing MongoDB adapter contract.

No MongoDB schema, database permissions, Koyeb configuration, Dockerfile, Procfile, or Telegram UI/search-result formatting was changed.

## AI Search Fix (2026-09-30)

- `ai_search/adapter.py`: person/filmography searches now query bounded title chunks instead of one oversized Mongo regex, deduplicate Media results, and respect `USE_CAPTION_FILTER`.
- `tests/ai_search/test_filmography.py`: updated the provider assertion for chunked filmography queries.
- No production bot handlers, MongoDB schema, deployment files, captions, buttons, pagination contract, or existing non-AI features were changed.
