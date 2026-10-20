import asyncio
import html
import logging
import mimetypes
import re
from urllib.parse import quote

from aiohttp import web as webserver
from info import LOG_CHANNEL
from plugins.stream_links import verify_signature, start_link_cleanup

routes = webserver.RouteTableDef()
CHUNK_SIZE = 1024 * 1024
logger = logging.getLogger(__name__)


async def bot_run(client=None):
    app = webserver.Application(client_max_size=30000000)
    app.add_routes(routes)
    if client is not None:
        app["bot"] = client
        start_link_cleanup(client)
    return app


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return webserver.json_response({"status": "ok", "service": "AK Filter stream server"})


def _media_details(message):
    for kind in ("video", "document", "audio", "animation"):
        media = getattr(message, kind, None)
        if media is not None:
            name = getattr(media, "file_name", None) or getattr(message, "caption", None) or f"telegram-{kind}"
            size = int(getattr(media, "file_size", 0) or 0)
            mime = getattr(media, "mime_type", None) or mimetypes.guess_type(name)[0] or "application/octet-stream"
            return str(name), size, str(mime)
    return None, 0, "application/octet-stream"


async def _get_message(request):
    message_id = int(request.match_info["message_id"])
    if not verify_signature(message_id, request.query.get("exp", ""), request.query.get("sig", "")):
        raise webserver.HTTPForbidden(text="Invalid or expired link.")
    client = request.app.get("bot")
    if client is None:
        raise webserver.HTTPServiceUnavailable(text="Streaming client is not ready.")
    message = await client.get_messages(LOG_CHANNEL, message_id)
    if not message or getattr(message, "empty", False):
        raise webserver.HTTPNotFound(text="File not found. It may have been removed from storage.")
    name, size, mime = _media_details(message)
    if not name or size <= 0:
        raise webserver.HTTPNotFound(text="This message does not contain downloadable media.")
    return client, message, name, size, mime


@routes.get("/watch/{message_id}/{filename}", allow_head=True)
@routes.get("/watch/{message_id}", allow_head=True)
async def watch_route(request):
    _, message, name, size, mime = await _get_message(request)
    message_id = int(request.match_info["message_id"])
    sig = request.query.get("sig", "")
    exp = request.query.get("exp", "")
    encoded_name = quote(name, safe="")
    suffix = f"?exp={quote(exp, safe='')}&sig={quote(sig, safe='')}"
    stream_url = f"/stream/{message_id}/{encoded_name}{suffix}"
    download_url = f"/download/{message_id}/{encoded_name}{suffix}"
    safe_name = html.escape(name)
    body = (
        "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{safe_name}</title><style>body{{margin:0;background:#101820;color:#fff;font-family:system-ui,sans-serif;"
        "display:flex;min-height:100vh;align-items:center;justify-content:center}main{width:min(960px,96vw)}"
        "video{width:100%;max-height:75vh;background:#000;border-radius:12px}"
        "a{display:inline-block;margin:14px 10px 0 0;padding:12px 18px;border-radius:9px;"
        "background:#28394b;color:#fff;text-decoration:none}p{color:#b9c5d2;overflow-wrap:anywhere}</style></head><body><main>"
        f"<h3>{safe_name}</h3><p>{size:,} bytes · {html.escape(mime)}</p>"
        f"<video controls playsinline preload='metadata' src='{stream_url}'></video><br>"
        f"<a href='{download_url}'>⬇ Download file</a><a href='{stream_url}'>Open direct stream</a>"
        "<p>Browser playback depends on format and codec support. If playback is unsupported, use Download or open the direct stream in a compatible player.</p>"
        "</main></body></html>"
    )
    return webserver.Response(text=body, content_type="text/html")


@routes.get("/stream/{message_id}/{filename}", allow_head=True)
@routes.get("/stream/{message_id}", allow_head=True)
@routes.get("/download/{message_id}/{filename}", allow_head=True)
@routes.get("/download/{message_id}", allow_head=True)
async def media_route(request):
    client, message, name, size, mime = await _get_message(request)
    is_download = request.path.startswith("/download/")
    start, end, status = 0, size - 1, 200
    range_header = request.headers.get("Range")
    if range_header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match or (not match.group(1) and not match.group(2)):
            raise webserver.HTTPRequestRangeNotSatisfiable(headers={"Content-Range": f"bytes */{size}"})
        if not match.group(1):
            suffix_length = int(match.group(2))
            if suffix_length <= 0:
                raise webserver.HTTPRequestRangeNotSatisfiable(headers={"Content-Range": f"bytes */{size}"})
            start = max(0, size - suffix_length)
        else:
            start = int(match.group(1))
            if match.group(2):
                end = int(match.group(2))
        if start >= size or end < start:
            raise webserver.HTTPRequestRangeNotSatisfiable(headers={"Content-Range": f"bytes */{size}"})
        end = min(end, size - 1)
        status = 206

    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Type": mime,
        "Cache-Control": "private, max-age=300",
        "Content-Disposition": ("attachment" if is_download else "inline") + f"; filename*=UTF-8''{quote(name, safe='')}",
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    response = webserver.StreamResponse(status=status, headers=headers)
    if request.method == "HEAD":
        await response.prepare(request)
        await response.write_eof()
        return response
    await response.prepare(request)

    first_chunk = start // CHUNK_SIZE
    last_chunk = end // CHUNK_SIZE
    chunk_limit = last_chunk - first_chunk + 1
    absolute = first_chunk * CHUNK_SIZE
    try:
        async for chunk in client.stream_media(message, offset=first_chunk, limit=chunk_limit):
            chunk_start = absolute
            chunk_end = chunk_start + len(chunk) - 1
            absolute += len(chunk)
            if chunk_end < start:
                continue
            if chunk_start > end:
                break
            left = max(0, start - chunk_start)
            right = min(len(chunk), end - chunk_start + 1)
            if right > left:
                await response.write(chunk[left:right])
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    except Exception:
        logger.exception("Telegram media streaming failed for message %s", getattr(message, "id", "?"))
    finally:
        try:
            await response.write_eof()
        except Exception:
            pass
    return response
