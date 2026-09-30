# AI Search

This package adds a deterministic, local AI-style query understanding layer to the existing movie/file search.

## Production behavior

- The existing MongoDB `Media` collection remains the source of files.
- Normal PM search uses the AI layer first for clearly understood queries.
- AI results are converted back to the original Media documents, so the existing Telegram UI/buttons/captions continue to work.
- If parsing is low-confidence, AI search fails, or AI finds nothing, the original `get_search_results()` implementation is used automatically.
- Pagination uses the same `(files, next_offset, total_results)` contract as the original search function.

No external AI API key is required by this implementation.
