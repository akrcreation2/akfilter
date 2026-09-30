"""Short-lived in-memory storage for AI discovery button results."""
from __future__ import annotations
import secrets
import time
from typing import Dict, List, Optional, Tuple
from .discovery import MovieCandidate

_STORE: Dict[str, Tuple[float, int, List[MovieCandidate]]] = {}
_TTL = 900


def put(user_id: int, movies: List[MovieCandidate]) -> str:
    token = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:10]
    _STORE[token] = (time.time(), int(user_id or 0), list(movies))
    return token


def get(token: str, user_id: int) -> Optional[List[MovieCandidate]]:
    item = _STORE.get(token)
    if not item:
        return None
    created, owner, movies = item
    if time.time() - created > _TTL:
        _STORE.pop(token, None)
        return None
    if owner not in (0, int(user_id or 0)):
        return None
    return list(movies)
