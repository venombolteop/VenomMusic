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
# Timed lines for a track do not change, and a queue replays the same songs.
# The API caches too, but a hit there still costs a round trip from here.
_lines_cache = {}
_LINES_CACHE_MAX = 128


def _cache_key(title: str, duration):
    return ((title or "").strip().lower(), int(duration or 0))


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
    key = _cache_key(track_title, duration)
    if key in _lines_cache:
        return _lines_cache[key]

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
                    _lines_cache[key] = []
                    return []
                data = await resp.json()
    except Exception as e:
        LOGGER(__name__).debug("lyrics lookup failed: %s: %s", type(e).__name__, e)
        return []
    lines = [(item["time"], item["text"]) for item in (data.get("lines") or [])]
    if len(_lines_cache) >= _LINES_CACHE_MAX:
        _lines_cache.clear()
    _lines_cache[key] = lines
    return lines


_call_cache = {}
_CALL_TTL = 600


async def _group_call(client, chat_id):
    """The active group call for a chat, or None when none is running.

    The handle lives on the full channel and does not change while a call
    runs, so it is read once and kept. Asking for it per line is what turned
    a synced display into a FLOOD_WAIT: two dozen GetFullChannel calls a song
    is far past what an account may make, and once Telegram starts refusing,
    no line goes out at all.
    """
    from pyrogram import raw
    from pyrogram.errors import RPCError

    hit = _call_cache.get(chat_id)
    if hit and hit[0] > time.time():
        return hit[1]

    try:
        peer = await client.resolve_peer(chat_id)
        full = await client.invoke(
            raw.functions.channels.GetFullChannel(channel=peer)
        )
    except RPCError as e:
        if "FLOOD" in str(e).upper():
            LOGGER(__name__).info("call lookup flood-limited for %s", chat_id)
        elif "CHANNEL_INVALID" not in str(e).upper():
            LOGGER(__name__).info("no call for %s: %s", chat_id, str(e)[:80])
        return None
    call = getattr(full.full_chat, "call", None)
    if call is not None:
        _call_cache[chat_id] = (time.time() + _CALL_TTL, call)
    return call


async def send_call_message(client, chat_id, text):
    """Post a message into the voice chat's own chat panel.

    This is a group-call message, not a chat message: it is delivered to the
    call itself and appears in the panel next to the participant list, so
    nothing lands in the group conversation and there is nothing to delete
    from it afterwards. Editing is not offered on these messages, so the
    display deletes the previous line and sends the next one.
    """
    from pyrogram import raw
    from pyrogram.errors import MessageIdInvalid, RPCError

    try:
        call = await _group_call(client, chat_id)
        if call is None:
            return None
        sent = await client.invoke(
            raw.functions.phone.SendGroupCallMessage(
                call=call,
                random_id=int(time.time() * 1000) % (2 ** 30),
                message=raw.types.TextWithEntities(
                    text=text, entities=[]
                ),
            )
        )
        for update in getattr(sent, "updates", []):
            message = getattr(update, "message", None)
            if message is not None:
                return message.id
        return 0
    except MessageIdInvalid:
        return None
    except RPCError as e:
        if "MESSAGE_TOO_LONG" in str(e).upper():
            LOGGER(__name__).info("call message too long, skipped")
        else:
            LOGGER(__name__).info(
                "call message not sent: %s", str(e)[:120]
            )
        return None
    except Exception as e:
        LOGGER(__name__).info(
            "call message failed: %s: %s", type(e).__name__, str(e)[:100]
        )
        return None


async def delete_call_message(client, chat_id, message_id):
    if not message_id:
        return
    from pyrogram import raw

    try:
        call = await _group_call(client, chat_id)
        if call is None:
            return
        await client.invoke(
            raw.functions.phone.DeleteGroupCallMessages(
                call=call, messages=[message_id]
            )
        )
    except Exception:
        pass


async def set_call_title(client, chat_id, text):
    """Rewrite the call header. Kept as a fallback for clients that render it."""
    from pyrogram import raw

    if not text:
        return
    try:
        call = await _group_call(client, chat_id)
        if call is None:
            return False
        await client.invoke(
            raw.functions.phone.EditGroupCallTitle(
                call=call, title=f"🎵 {text}"[:64]
            )
        )
        return True
    except Exception as e:
        LOGGER(__name__).info(
            "call title not set: %s: %s", type(e).__name__, str(e)[:100]
        )
        return False


async def _run(chat_id, message, lines, started_at, client=None, title=True):
    """Show each line in the call's chat panel as the song reaches it.

    A group-call message cannot be edited, so one is sent per line and the
    previous one deleted: the panel shows the line being sung rather than a
    growing transcript, and the chat keeps no record of it.
    """
    shown = None
    try:
        for when, text in lines:
            wait = when - (time.monotonic() - started_at)
            if wait > 0:
                await asyncio.sleep(wait)
            elif wait < -30:
                continue
            if client is not None:
                if shown:
                    await delete_call_message(client, chat_id, shown)
                    shown = None
                shown = await send_call_message(client, chat_id, text)
            if message is not None:
                try:
                    await message.edit_text(f"🎵 <b>{text}</b>", parse_mode=None)
                except Exception:
                    message = None
    except asyncio.CancelledError:
        raise
    except Exception as e:
        LOGGER(__name__).info(
            "lyrics display stopped: %s: %s", type(e).__name__, e
        )
    finally:
        if client is not None and shown:
            asyncio.create_task(delete_call_message(client, chat_id, shown))


async def start(client, chat_id, track_title, duration=None,
                post_message: bool = True, use_title: bool = True,
                playback_started: float | None = None):
    """Drive the synced display for the track that just started.

    `use_title` writes each line into the voice chat header, which is the only
    surface inside the call itself; `post_message` additionally keeps one
    editable message in the chat, which is what a reader in the chat wants.
    """
    stop(chat_id)
    lines = await fetch(track_title, duration)
    if not lines:
        LOGGER(__name__).info("lyrics: none found for %r", track_title[:50])
        return None
    # `playback_started` is when the audio actually began, in the caller's
    # monotonic clock. The lookup above took time, and counting from here
    # instead leaves the whole display permanently that far behind the singing.
    started_at = playback_started or time.monotonic()

    message = None
    if post_message:
        try:
            message = await client.send_message(
                chat_id, "🎵 …", disable_web_page_preview=True
            )
        except Exception as e:
            LOGGER(__name__).debug(
                "could not post lyrics message: %s: %s", type(e).__name__, e
            )
    task = asyncio.create_task(
        _run(chat_id, message, lines, started_at, client, use_title)
    )
    _timers[chat_id] = (task, message)
    LOGGER(__name__).info(
        "lyrics live in %s: %d lines for %r", chat_id, len(lines), track_title[:40]
    )
    return message


def forget(chat_id):
    _call_cache.pop(chat_id, None)


def stop(chat_id):
    entry = _timers.pop(chat_id, None)
    if not entry:
        return
    task, message = entry
    if not task.done():
        task.cancel()
