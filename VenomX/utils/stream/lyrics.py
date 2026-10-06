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
from pyrogram.types import LinkPreviewOptions

from VenomX import LOGGER


def no_preview():
    """Send with the link preview off.

    `disable_web_page_preview` is the old spelling and pyrogram now takes the
    options object; the flag still works but is on its way out.
    """
    return LinkPreviewOptions(is_disabled=True)

LRC_LINE = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")

_timers = {}
# Timed lines for a track do not change, and a queue replays the same songs.
# The API caches too, but a hit there still costs a round trip from here.
_lines_cache = {}
_LINES_CACHE_MAX = 128


def _cache_key(title: str, duration, lang=None):
    return ((title or "").strip().lower(), int(duration or 0), (lang or "auto").lower())


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


async def fetch(track_title: str, duration: int | None = None, lang: str | None = None,
                chat_id: int | None = None):
    """Timed lines for a track, as [(seconds, line)].

    The lookup, the title cleanup, the length matching and the language choice
    all live in the media API, so the answer arrives ready to play against.
    """
    if lang is None and chat_id is not None:
        try:
            from VenomX.utils.database import get_lyrics_lang

            lang = await get_lyrics_lang(chat_id)
        except Exception:
            lang = None
    key = _cache_key(track_title, duration, lang)
    if key in _lines_cache:
        return _lines_cache[key]

    base = (getattr(config, "VENOM_API_URL", "") or "").strip()
    if not base:
        return []
    payload = {"title": track_title}
    if duration:
        payload["duration"] = int(duration)
    if lang and lang != "auto":
        payload["lang"] = lang
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


NOTES = ("🎵", "🎶", "♫", "🎼", "🎧", "🔊")

# Floor between two panel rewrites. A group-call message cannot be edited, so
# replacing one is a send plus a delete, and a song of forty lines is eighty
# requests — the account gets rate-limited and then nothing shows at all.
def _min_refresh() -> float:
    return float(getattr(config, "VC_LYRICS_MIN_SEC", 4) or 4)


# A safety rail, not a display setting. Every line is one request to Telegram,
# and an account that leans on it hard gets rate-limited — after which the
# panel, the session and the play commands all stop until the wait expires.
# This caps the burst per minute and per track so a long queue cannot walk
# into that.
_BURST_PER_MINUTE = 12
_MAX_PER_TRACK = 45
_sent_times = {}
_sent_this_track = {}


def _budget_left(chat_id: int) -> bool:
    now = time.monotonic()
    history = [t for t in _sent_times.get(chat_id, []) if now - t < 60]
    _sent_times[chat_id] = history
    if len(history) >= _BURST_PER_MINUTE:
        return False
    if _sent_this_track.get(chat_id, 0) >= _MAX_PER_TRACK:
        return False
    return True


def _count_sent(chat_id: int):
    _sent_times.setdefault(chat_id, []).append(time.monotonic())
    _sent_this_track[chat_id] = _sent_this_track.get(chat_id, 0) + 1


def new_track(chat_id: int):
    _sent_this_track[chat_id] = 0


async def _run(chat_id, message, lines, started_at, client=None, title=True):  # noqa: C901
    """Show each line in the call's chat panel as the song reaches it.

    One message per line, kept rather than replaced: these messages cannot be
    edited, so removing the previous line costs a second request per line and
    a long song then walks the account into a flood wait. Letting them stack
    costs one request each and reads as a running transcript of the call,
    which is what a synced display should look like anyway.
    """
    gap_after = max(float(getattr(config, "VC_LYRICS_GAP_SEC", 8) or 8), 3.0)
    try:
        for index, (when, text) in enumerate(lines):
            wait = when - (time.monotonic() - started_at)
            if wait > 0:
                # A long stretch between two lines is an instrumental break, and
                # an empty panel through it reads as the bot having dropped.
                # Notes fill the gap so the panel keeps moving.
                if wait > gap_after:
                    await _fill_gap(client, chat_id, wait, started_at + when)
                else:
                    await asyncio.sleep(wait)
            elif wait < -30:
                continue
            if client is not None:
                # One request per line. The floor is a safety margin, not a
                # display setting: lines closer together than this are skipped
                # so a burst cannot outrun the account's rate limit.
                left = (started_at + when) - time.monotonic()
                if 0 < left < _min_refresh():
                    continue
                if not _budget_left(chat_id):
                    continue
                _count_sent(chat_id)
                await send_call_message(client, chat_id, text)
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
        pass


async def _fill_gap(client, chat_id, wait, due_at):
    """Cover the silence between two lines with notes until the next one."""
    if client is None:
        await asyncio.sleep(wait)
        return

    step = max(float(getattr(config, "VC_LYRICS_GAP_SEC", 8) or 8), 3.0)
    index = 0
    try:
        while True:
            left = due_at - time.monotonic()
            if left <= 0.4:
                return
            if _budget_left(chat_id):
                _count_sent(chat_id)
                mark = " ".join(NOTES[index % len(NOTES)] for _ in range(2))
                index += 1
                await send_call_message(client, chat_id, mark)
            await asyncio.sleep(max(min(step, max(left - 0.4, 0.4)), _min_refresh()))
    except asyncio.CancelledError:
        raise
    except Exception as e:
        LOGGER(__name__).info("gap fill stopped: %s: %s", type(e).__name__, e)


async def _run_notes(client, chat_id, track_title, duration, playback_started):
    """Stand in for lyrics on a track that has none.

    An empty call panel reads as a bot that joined and stopped, which is worse
    than no lyrics at all — so the panel keeps a note appearing for as long as
    the track plays, and stops when the track does. Notes are sent, not
    replaced: removing the previous one costs another request for no gain.
    """
    index = 0
    step = max(float(getattr(config, "VC_LYRICS_NOTES_SEC", 30) or 30), 10.0)
    try:
        while True:
            if _budget_left(chat_id):
                _count_sent(chat_id)
                mark = " ".join(NOTES[index % len(NOTES)] for _ in range(2))
                index += 1
                await send_call_message(client, chat_id, mark)
            await asyncio.sleep(step)
            if duration and (time.monotonic() - playback_started) > float(duration) + 5:
                break
    except asyncio.CancelledError:
        raise
    except Exception as e:
        LOGGER(__name__).info("notes display stopped: %s: %s", type(e).__name__, e)


async def start(client, chat_id, track_title, duration=None,
                post_message: bool = True, use_title: bool = True,
                playback_started: float | None = None):
    """Drive the synced display for the track that just started.

    `use_title` writes each line into the voice chat header, which is the only
    surface inside the call itself; `post_message` additionally keeps one
    editable message in the chat, which is what a reader in the chat wants.

    The per-chat switch is read here as well as by the caller, so every path
    that shows something in the panel goes through the same gate: turning it
    off in a chat stops the lines, the gap notes and the chat message, and
    only in that chat.
    """
    stop(chat_id)
    new_track(chat_id)
    try:
        from VenomX.utils.database import get_vc_lyrics

        if not await get_vc_lyrics(chat_id):
            LOGGER(__name__).info("lyrics off for chat %s, nothing posted", chat_id)
            return None
    except Exception as e:
        LOGGER(__name__).info(
            "lyrics setting unreadable for %s: %s: %s",
            chat_id, type(e).__name__, e,
        )
        return None
    lines = await fetch(track_title, duration, chat_id=chat_id)
    started_at = playback_started or time.monotonic()
    if not lines:
        LOGGER(__name__).info("lyrics: none found for %r", track_title[:50])
        if getattr(config, "VC_LYRICS_NOTES", "True") in (True, "True", "true"):
            task = asyncio.create_task(
                _run_notes(client, chat_id, track_title, duration, started_at)
            )
            _timers[chat_id] = (task, None)
            return None
        return None
    # `playback_started` is when the audio actually began, in the caller's
    # monotonic clock. The lookup above took time, and counting from here
    # instead leaves the whole display permanently that far behind the singing.

    message = None
    if post_message:
        try:
            message = await client.send_message(
                chat_id, "🎵 …", link_preview_options=no_preview()
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


async def clear_panel(client, chat_id):
    """Remove this session's panel messages. Only used on an explicit reset."""
    return await delete_call_message(client, chat_id, None)


def forget(chat_id):
    _call_cache.pop(chat_id, None)


def stop(chat_id):
    entry = _timers.pop(chat_id, None)
    if not entry:
        return
    task, message = entry
    if not task.done():
        task.cancel()
