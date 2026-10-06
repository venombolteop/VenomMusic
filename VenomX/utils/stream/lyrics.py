# All rights reserved.
#

"""Time-synced lyrics for whatever is playing in a voice chat.

The lines come from the media API, which holds the title cleanup and the
length matching. A message is posted by the assistant and rewritten as the
song reaches each line — one message edited in place, because a track with
forty lines would otherwise bury the chat.
"""

import asyncio
import re
import time

import aiohttp

import config
from VenomX import LOGGER

LRC_LINE = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")

_timers = {}


def parse_lrc(raw: str):
    """Turn timed lyrics into [(seconds, line)] in playback order."""
    if not raw:
        return []
    entries = []
    for raw_line in raw.splitlines():
        stamps = LRC_LINE.findall(raw_line.strip())
        if not stamps:
            continue
        text = LRC_LINE.sub("", raw_line).strip()
        if not text:
            continue
        for minutes, seconds, fraction in stamps:
            total = int(minutes) * 60 + int(seconds)
            if fraction:
                total += int(fraction.ljust(3, "0")) / 1000
            entries.append((total, text))
    entries.sort(key=lambda item: item[0])
    return entries


async def fetch(track_title: str, duration: int | None = None):
    """Timed lines for a track, as [(seconds, line)].

    The lookup, the title cleanup and the length matching all live in the
    media API, so the answer arrives ready to play against.
    """
    base = (getattr(config, "VENOM_API_URL", "") or "").strip()
    if not base:
        return []
    payload = {"title": track_title}
    if duration:
        payload["duration"] = int(duration)
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20)
        ) as session:
            async with session.post(
                f"{base.rstrip('/')}/v1/lyrics",
                json=payload,
                headers={"accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception as e:
        LOGGER(__name__).debug("lyrics lookup failed: %s: %s", type(e).__name__, e)
        return []
    return [(item["time"], item["text"]) for item in (data.get("lines") or [])]


async def _run(chat_id, message, lines, started_at):
    """Rewrite one message as the playback reaches each line."""
    try:
        for when, text in lines:
            wait = when - (time.monotonic() - started_at)
            if wait > 0:
                await asyncio.sleep(wait)
            elif wait < -30:
                continue
            try:
                await message.edit_text(f"🎵 <b>{text}</b>", parse_mode=None)
            except Exception:
                break
    except asyncio.CancelledError:
        raise
    except Exception as e:
        LOGGER(__name__).debug("lyrics display stopped: %s: %s", type(e).__name__, e)


async def start(client, chat_id, track_title, duration=None):
    """Post and drive a lyrics message for the track that just started."""
    stop(chat_id)
    lines = await fetch(track_title, duration)
    if not lines:
        LOGGER(__name__).info("lyrics: none found for %r", track_title[:50])
        return None
    try:
        message = await client.send_message(chat_id, "🎵 …", disable_web_page_preview=True)
    except Exception as e:
        LOGGER(__name__).debug("could not post lyrics message: %s: %s", type(e).__name__, e)
        return None
    task = asyncio.create_task(_run(chat_id, message, lines, time.monotonic()))
    _timers[chat_id] = (task, message)
    LOGGER(__name__).info(
        "lyrics live in %s: %d lines for %r", chat_id, len(lines), track_title[:40]
    )
    return message


def stop(chat_id):
    entry = _timers.pop(chat_id, None)
    if not entry:
        return
    task, message = entry
    if not task.done():
        task.cancel()
