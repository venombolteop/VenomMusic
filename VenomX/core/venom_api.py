# All rights reserved.
#

"""Client for the Venom media API (https://api.tomatofist.com).

Why this exists
---------------
VenomMusic can already pull a YouTube track with yt-dlp in-process. This is not
a replacement for that — it is the option to take the fetch off this box. The
API already holds a signed-in session and a warm disk cache, so a popular track
is a local read on its side and never reaches YouTube at all, which is the part
that is actually hard to do here.

Deliberately small: one file, no plugin, no monkey-patching of the existing
download path. If it works, wiring it into a handler is a one-line change; if it
does not, deleting this file is the whole revert.

The one thing worth knowing before using it
-------------------------------------------
`link()` returns a URL and `download()` fetches bytes, and they are not
interchangeable:

  * `stream_url` points at this project's own /stream/<id> permalink. It works
    from any host and does not expire, so it is the safe thing to hand to
    Telegram, a player, or a user.
  * It serves the media with `content-disposition: inline`, so a browser plays
    it rather than saving it. Add `attachment=1` when you want a file.

`POST /v1/download` returns bytes directly. That is the one to call when the
bytes are going into a Pyrogram upload, because it avoids a second hop through
the public internet.

Config
------
    VENOM_API_URL   base URL, default https://api.tomatofist.com
    VENOM_API_KEY   optional. The API is open and needs no key; send one only if
                    you want per-account usage counted against a plan.

No key is required, and nothing here reads a Telegram session, a cookie jar, or
yt-dlp's arguments — that is the API's business, not the caller's.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

import aiohttp

from ..logging import LOGGER

DEFAULT_BASE_URL = "https://api.tomatofist.com"


class VenomApiError(Exception):
    """A failure the API described.

    `code` is its machine code (`not_found`, `invalid_request`, …) and
    `error_id` is the opaque id to quote if the failure needs looking at. Both
    are preserved rather than flattened into a string, because a caller usually
    wants to branch on one of them.
    """

    def __init__(self, status: int, code: str, message: str, error_id: str | None = None):
        super().__init__(f"[{status} {code}] {message}")
        self.status = status
        self.code = code
        self.message = message
        self.error_id = error_id


class VenomApi:
    """Async client. One instance per process is plenty; aiohttp keeps the pool.

    Use it as an async context manager so the session is always closed:

        async with VenomApi() as api:
            info = await api.link("https://youtu.be/xxxx")
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: int = 300):
        self.base_url = (base_url or os.getenv("VENOM_API_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("VENOM_API_KEY")
        # Generous: a cold video download is a real fetch, not a metadata call.
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    # ── plumbing ──────────────────────────────────────────────────────────

    async def __aenter__(self) -> "VenomApi":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def start(self) -> "VenomApi":
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    def _headers(self) -> dict[str, str]:
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    @staticmethod
    def _raise_for_error(status: int, payload: Any) -> None:
        """Turn the API's error envelope into an exception.

        The envelope is always `{"error": {code, message, error_id}}`, and the
        404 handler adds `suggestion` and `endpoints`, which is why the whole
        object is carried on the exception rather than just the message — a
        caller that mistyped a path can recover from it.
        """
        err = (payload or {}).get("error") if isinstance(payload, dict) else None
        if not isinstance(err, dict):
            raise VenomApiError(status, "unknown", f"HTTP {status}", None)
        exc = VenomApiError(
            status,
            str(err.get("code") or "error"),
            str(err.get("message") or ""),
            err.get("error_id"),
        )
        exc.payload = err
        raise exc

    async def _json(self, method: str, path: str, **kwargs) -> dict:
        await self.start()
        url = self.base_url + path
        async with self._session.request(method, url, headers=self._headers(),
                                         **kwargs) as resp:
            try:
                payload = await resp.json(content_type=None)
            except Exception:
                payload = None
            if resp.status >= 400:
                self._raise_for_error(resp.status, payload)
            return payload if isinstance(payload, dict) else {}

    # ── endpoints ─────────────────────────────────────────────────────────

    async def health(self) -> dict:
        """Dependency state. `checks` values are statuses only, by design."""
        return await self._json("GET", "/health")

    async def resolve(self, url: str) -> dict:
        """Full metadata for one video. POST, because a URL is not a nice
        query parameter and this is the call a program makes."""
        return await self._json("POST", "/v1/resolve",
                                json={"url": url})

    async def search(self, query: str, limit: int = 5) -> dict:
        """Search YouTube. `engine` is 'primary' or 'fallback'."""
        return await self._json("POST", "/v1/search",
                                json={"q": query, "limit": limit})

    async def formats(self, url: str) -> dict:
        """Every selectable format, split into `audio` and `video`."""
        return await self._json("POST", "/v1/formats", json={"url": url})

    async def link(self, url: str, kind: str = "audio",
                   height: int | None = None) -> dict:
        """Resolve to a URL instead of the bytes.

        Returns exactly three fields: `title`, `type`, `stream_url`.

        GET rather than POST, because the answer is a link and a link is
        something you can paste into a message, a log, or an <audio> tag.
        """
        params: dict[str, Any] = {"url": url, "type": kind}
        if height:
            params["height"] = height
        if kind == "audio":
            # The permalink defaults to mp3 already; naming it keeps the
            # returned URL self-describing.
            params["convert"] = "mp3"
        return await self._json("GET", "/v1/link", params=params)

    async def stream_url(self, url: str, kind: str = "audio",
                         height: int | None = None) -> Optional[str]:
        """Just the URL, or None if the video could not be resolved.

        The narrow helper most callers want: it swallows the "no such video"
        case so a handler can fall through to its existing yt-dlp path instead
        of raising through a message handler.
        """
        try:
            data = await self.link(url, kind=kind, height=height)
        except VenomApiError as exc:
            if exc.status in (400, 403, 404):
                LOGGER(__name__).warning(
                    f"Venom API could not resolve {url}: {exc.code}")
                return None
            raise
        return data.get("stream_url")

    async def warm(self, url: str, kind: str = "audio",
                   height: int | None = None) -> dict:
        """Fetch it into the API's cache now, get no bytes back.

        Worth calling before a user asks: afterwards the real request is a disk
        read on the other side. Returns `took_seconds` and `already_cached`, so
        a caller can log whether warming was worth anything.
        """
        params: dict[str, Any] = {"url": url, "type": kind}
        if height:
            params["height"] = height
        return await self._json("GET", "/warm", params=params)

    async def download(self, url: str, kind: str = "audio", convert: str = "mp3",
                       height: int | None = None) -> tuple[bytes, str]:
        """The media itself, as (bytes, filename). For a Pyrogram upload.

        POST with `link=0` semantics — POST always returns bytes. Note this
        holds the whole file in memory; there is `download_to` for when that
        does not fit.
        """
        payload: dict[str, Any] = {"url": url, "type": kind}
        if kind == "audio":
            payload["convert"] = convert
        if height:
            payload["height"] = height

        await self.start()
        async with self._session.post(
                self.base_url + "/v1/download", headers=self._headers(),
                json=payload) as resp:
            if resp.status >= 400:
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    body = None
                self._raise_for_error(resp.status, body)
            data = await resp.read()
            name = self._filename_from(resp.headers.get("content-disposition"))
            return data, name

    async def download_to(self, url: str, path: str, kind: str = "audio",
                          convert: str = "mp3", height: int | None = None) -> str:
        """Stream the media to `path`. Returns the path.

        Use this rather than `download` for anything large: a long video is tens
        of megabytes, and a music bot serving several at once will not fit that
        in memory comfortably.
        """
        payload: dict[str, Any] = {"url": url, "type": kind}
        if kind == "audio":
            payload["convert"] = convert
        if height:
            payload["height"] = height

        await self.start()
        async with self._session.post(
                self.base_url + "/v1/download", headers=self._headers(),
                json=payload) as resp:
            if resp.status >= 400:
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    body = None
                self._raise_for_error(resp.status, body)

            disposition = resp.headers.get("content-disposition", "")
            written = 0
            with open(path, "wb") as fh:
                async for chunk in resp.content.iter_chunked(65536):
                    fh.write(chunk)
                    written += len(chunk)
        LOGGER(__name__).info(
            f"Venom API wrote {written} bytes to {path} ({disposition})")
        return path

    @staticmethod
    def _filename_from(disposition: str | None) -> str:
        """Pull the filename out of a Content-Disposition header."""
        if not disposition:
            return "download"
        for part in disposition.split(";"):
            part = part.strip()
            if part.lower().startswith("filename="):
                return part.split("=", 1)[1].strip().strip('"') or "download"
        return "download"


async def check(verbose: bool = True) -> bool:
    """One call that proves the API is reachable and serving.

    Meant to be callable from a plugin's health path or a test, so the answer is
    a bool rather than an exception. Returns False instead of raising: a music
    bot must not die because an optional dependency is down.
    """
    try:
        async with VenomApi(timeout=30) as api:
            data = await api.health()
            if verbose:
                LOGGER(__name__).info(f"Venom API: {data.get('status')} {data.get('checks')}")
            return bool(data.get("ok"))
    except Exception as exc:  # noqa: BLE001
        if verbose:
            LOGGER(__name__).warning(f"Venom API unreachable: {type(exc).__name__}: {exc}")
        return False


if __name__ == "__main__":
    # `python3 -m VenomX.core.venom_api` from the project root.
    async def _main() -> None:
        print("health :", asyncio.run(check()))

    asyncio.run(_main())
