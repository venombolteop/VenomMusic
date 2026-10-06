# All rights reserved.
#

"""Live test for VenomX/core/venom_api.py.

    cd /home/ubuntu/VenomMusic && ./.venv/bin/python -m tools.test_venom_api

Hits the real API — nothing is mocked, because the only thing worth testing
here is whether the real thing works. Downloads land in /tmp and are deleted.

Exits non-zero if any check fails, so it can be run from CI or a cron without
being read.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time

from VenomX.core.venom_api import VenomApi, VenomApiError

VIDEO = os.getenv("VENOM_TEST_VIDEO", "aqz-KE-bpKQ")   # Big Buck Bunny
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO}"

passed = 0
failed = 0


def ok(label: str) -> None:
    global passed
    passed += 1
    print(f"  \033[32mPASS\033[0m  {label}")


def bad(label: str, detail: str = "") -> None:
    global failed
    failed += 1
    print(f"  \033[31mFAIL\033[0m  {label}" + (f"  — {detail}" if detail else ""))


def check(label: str, condition: bool, detail: str = "") -> None:
    ok(label) if condition else bad(label, detail)


async def main() -> int:
    print(f"\n\033[1mVenom API client — live test against the real service\033[0m\n")

    async with VenomApi() as api:
        print(f"  base_url: {api.base_url}")
        print(f"  api_key : {'set' if api.api_key else 'not set (the API is open)'}\n")

        # ── health ────────────────────────────────────────────────────────
        try:
            t0 = time.monotonic()
            health = await api.health()
            ms = int((time.monotonic() - t0) * 1000)
            check("health responds", isinstance(health, dict), str(health)[:80])
            check(f"health ok ({ms}ms)", health.get("ok") is True,
                  f"status={health.get('status')}")
            checks = health.get("checks") or {}
            # The endpoint reports statuses only, on purpose.
            allowed = {"ok", "MISSING", "NOT FOUND", "unavailable", "unreachable", "ready"}
            stray = {k: v for k, v in checks.items() if v not in allowed}
            check("health leaks no paths or config", not stray, str(stray)[:80])
        except Exception as exc:  # noqa: BLE001
            bad("health responds", f"{type(exc).__name__}: {exc}")
            print("\n  API unreachable — nothing else can be tested.\n")
            return 1

        # ── resolve ───────────────────────────────────────────────────────
        try:
            t0 = time.monotonic()
            info = await api.resolve(VIDEO_URL)
            ms = int((time.monotonic() - t0) * 1000)
            check(f"resolve returns metadata ({ms}ms)",
                  bool(info.get("id")) and bool(info.get("title")),
                  str(info)[:100])
            print(f"        title: {info.get('title')}")
        except Exception as exc:  # noqa: BLE001
            bad("resolve returns metadata", f"{type(exc).__name__}: {exc}")

        # ── search ────────────────────────────────────────────────────────
        try:
            data = await api.search("blender open movie", limit=3)
            check("search returns results",
                  data.get("count", 0) >= 1, str(data)[:100])
            check("search names its source",
                  data.get("engine") in ("primary", "fallback"),
                  f"engine={data.get('engine')!r}")
            print(f"        {data.get('count')} results via {data.get('engine')}")
        except Exception as exc:  # noqa: BLE001
            bad("search returns results", f"{type(exc).__name__}: {exc}")

        # ── formats ───────────────────────────────────────────────────────
        try:
            data = await api.formats(VIDEO_URL)
            n = len(data.get("video") or [])
            check("formats lists something", (n + len(data.get("audio") or [])) >= 1,
                  str(data)[:100])
            print(f"        {n} video, {len(data.get('audio') or [])} audio-only")
        except Exception as exc:  # noqa: BLE001
            bad("formats lists something", f"{type(exc).__name__}: {exc}")

        # ── link ──────────────────────────────────────────────────────────
        try:
            data = await api.link(VIDEO_URL, kind="audio")
            # Exactly three fields. Anything more is us exposing internals.
            check("link returns exactly {title, type, stream_url}",
                  set(data) == {"title", "type", "stream_url"}, str(sorted(data)))
            check("link stream_url uses the /stream route",
                  "/stream/" in (data.get("stream_url") or ""),
                  str(data.get("stream_url")))
            print(f"        title     : {data.get('title')}")
            print(f"        stream_url: {data.get('stream_url')}")
        except Exception as exc:  # noqa: BLE001
            bad("link returns the three fields", f"{type(exc).__name__}: {exc}")

        # ── stream_url helper ─────────────────────────────────────────────
        try:
            su = await api.stream_url(VIDEO_URL, kind="audio")
            check("stream_url helper returns a URL", bool(su), repr(su))
            check("stream_url helper returns None for a bad id, not an exception",
                  await api.stream_url("https://youtu.be/aaaaaaaaaaa") is None)
        except Exception as exc:  # noqa: BLE001
            bad("stream_url helper", f"{type(exc).__name__}: {exc}")

        # ── errors carry a code ───────────────────────────────────────────
        try:
            await api.resolve("https://www.youtube.com/watch?v=aaaaaaaaaaa")
            bad("a dead video raises", "no exception raised")
        except VenomApiError as exc:
            check("a dead video raises VenomApiError", exc.status in (400, 404),
                  f"status={exc.status}")
            check("the error carries a machine code", bool(exc.code), exc.code)
            check("the error message is not an internal traceback",
                  "Traceback" not in exc.message and "/home/" not in exc.message,
                  exc.message[:80])
            print(f"        code={exc.code} message={exc.message[:60]!r}")
        except Exception as exc:  # noqa: BLE001
            bad("a dead video raises VenomApiError", f"{type(exc).__name__}: {exc}")

        try:
            await api.download(VIDEO_URL, kind="audio", convert="mp4")
            bad("an impossible convert is rejected", "no exception raised")
        except VenomApiError as exc:
            check("an impossible convert is rejected with 422", exc.status == 422,
                  f"status={exc.status}")
        except Exception as exc:  # noqa: BLE001
            bad("an impossible convert is rejected", f"{type(exc).__name__}: {exc}")

        # ── the bytes, streamed to disk ───────────────────────────────────
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "track.mp3")

            try:
                t0 = time.monotonic()
                await api.download_to(VIDEO_URL, path, kind="audio", convert="mp3")
                secs = time.monotonic() - t0
                size = os.path.getsize(path)
                check(f"download_to wrote a file ({size} bytes, {secs:.2f}s)",
                      size > 10_000, f"{size} bytes")
                with open(path, "rb") as fh:
                    head = fh.read(3)
                check("the file is an mp3 (ID3 header)", head == b"ID3", repr(head))
            except Exception as exc:  # noqa: BLE001
                bad("download_to wrote a file", f"{type(exc).__name__}: {exc}")

            # Video, so the client is exercised for both kinds.
            vpath = os.path.join(tmp, "clip.mp4")
            try:
                await api.download_to(VIDEO_URL, vpath, kind="video")
                size = os.path.getsize(vpath)
                check(f"video download works ({size} bytes)", size > 10_000)
            except Exception as exc:  # noqa: BLE001
                bad("video download works", f"{type(exc).__name__}: {exc}")

        # ── in-memory download, small file only ───────────────────────────
        try:
            data, name = await api.download(VIDEO_URL, kind="audio", convert="mp3")
            check(f"download() returned bytes ({len(data)})", len(data) > 10_000)
            check("download() returned a filename", bool(name) and name != "download",
                  name)
            print(f"        filename: {name}")
        except Exception as exc:  # noqa: BLE001
            bad("download() returned bytes", f"{type(exc).__name__}: {exc}")

        # ── warm ──────────────────────────────────────────────────────────
        try:
            t0 = time.monotonic()
            data = await api.warm(VIDEO_URL, kind="audio")
            secs = time.monotonic() - t0
            check(f"warm primed the cache ({secs:.2f}s, "
                  f"already_cached={data.get('already_cached')})",
                  isinstance(data.get("bytes"), int))
            check("warm returned a usable stream_url",
                  "/stream/" in (data.get("stream_url") or ""),
                  str(data.get("stream_url")))

            # And the point of warming: the next request is fast.
            t0 = time.monotonic()
            await api.download_to(VIDEO_URL,
                                  os.path.join(tempfile.gettempdir(), "_vt_warm.mp3"),
                                  kind="audio", convert="mp3")
            warm_secs = time.monotonic() - t0
            try:
                os.remove(os.path.join(tempfile.gettempdir(), "_vt_warm.mp3"))
            except OSError:
                pass
            check(f"a download after warm is fast ({warm_secs:.2f}s)",
                  warm_secs < 5.0, f"{warm_secs:.2f}s")
        except Exception as exc:  # noqa: BLE001
            bad("warm primed the cache", f"{type(exc).__name__}: {exc}")

    print(f"\n\033[1m{passed} passed, {failed} failed\033[0m\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
