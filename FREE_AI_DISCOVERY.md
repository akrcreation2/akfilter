# Free AI Movie Discovery

This version does not require an OpenAI API key.

Discovery and file search are intentionally separate:

1. User sends natural-language movie/person query.
2. Parser extracts a likely person/entity.
3. Public metadata is queried and cached locally.
4. Movie titles/years are presented as buttons.
5. Only after a button click does the existing bot file/database search run.

The public metadata layer is best-effort and should be treated as discovery, not as the source of actual Telegram files.
