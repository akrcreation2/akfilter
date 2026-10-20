"""Temporary signed stream/download links with automatic 24-hour expiry."""
import asyncio
import hashlib
import hmac
import os
import time
from urllib.parse import quote
from info import BOT_TOKEN, KEEP_ALIVE_URL, LOG_CHANNEL

_BASE_URL = (os.environ.get("STREAM_URL") or os.environ.get("KEEP_ALIVE_URL") or KEEP_ALIVE_URL).rstrip("/")
_SECRET = os.environ.get("STREAM_SECRET") or BOT_TOKEN
LINK_TTL_SECONDS = 24 * 60 * 60
_CLEANUP_INTERVAL = 15 * 60
# file_id -> {message_id, expires_at}; expired entries are purged automatically.
_CACHE = {}
_LOCKS = {}
_CLEANUP_TASK = None

def _signature(message_id, expires_at):
    payload = f"{int(message_id)}:{int(expires_at)}".encode()
    return hmac.new(_SECRET.encode(), payload, hashlib.sha256).hexdigest()[:32]

def verify_signature(message_id, expires_at, signature):
    try:
        expiry = int(expires_at)
    except (TypeError, ValueError):
        return False
    if expiry <= int(time.time()) or not signature:
        return False
    expected = _signature(message_id, expiry)
    return hmac.compare_digest(expected, str(signature))

def _urls(message_id, file_name, expires_at):
    sig = _signature(message_id, expires_at)
    name = quote(file_name or "file", safe="")
    suffix = f"?exp={int(expires_at)}&sig={sig}"
    return (f"{_BASE_URL}/watch/{int(message_id)}/{name}{suffix}",
            f"{_BASE_URL}/download/{int(message_id)}/{name}{suffix}")

async def create_stream_links(client, file_id, file_name="file"):
    """Create/reuse a Telegram storage copy and return links valid for 24 hours."""
    if not _BASE_URL or not _SECRET:
        raise RuntimeError("Set STREAM_URL to the public HTTPS URL of this service.")
    key = str(file_id)
    now = int(time.time())
    cached = _CACHE.get(key)
    if cached and cached["expires_at"] > now:
        return (*_urls(cached["message_id"], file_name, cached["expires_at"]), cached["expires_at"])
    lock = _LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        now = int(time.time())
        cached = _CACHE.get(key)
        if cached and cached["expires_at"] > now:
            return (*_urls(cached["message_id"], file_name, cached["expires_at"]), cached["expires_at"])
        if cached and cached["expires_at"] <= now:
            _CACHE.pop(key, None)
            try:
                await client.delete_messages(LOG_CHANNEL, cached["message_id"])
            except Exception:
                pass
        copied = await client.send_cached_media(chat_id=LOG_CHANNEL, file_id=file_id)
        if not getattr(copied, "id", None):
            raise RuntimeError("Telegram did not return a stored media message.")
        expiry = int(time.time()) + LINK_TTL_SECONDS
        _CACHE[key] = {"message_id": int(copied.id), "expires_at": expiry}
        return (*_urls(copied.id, file_name, expiry), expiry)

async def cleanup_expired_links(client):
    """Periodically purge expired link records and temporary Telegram copies."""
    while True:
        try:
            now = int(time.time())
            expired_keys = [key for key, value in list(_CACHE.items()) if value["expires_at"] <= now]
            for key in expired_keys:
                entry = _CACHE.pop(key, None)
                if entry:
                    try:
                        await client.delete_messages(LOG_CHANNEL, entry["message_id"])
                    except Exception:
                        # Link still expires cryptographically even if Telegram cleanup fails.
                        pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(_CLEANUP_INTERVAL)

def start_link_cleanup(client):
    global _CLEANUP_TASK
    if _CLEANUP_TASK is None or _CLEANUP_TASK.done():
        _CLEANUP_TASK = asyncio.create_task(cleanup_expired_links(client))
