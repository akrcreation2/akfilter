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
