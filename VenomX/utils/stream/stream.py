
# All rights reserved.
#

import asyncio
import aiohttp
import logging
import os
import time as _time
from functools import partial
from urllib.parse import urlencode
from VenomX.utils.stream.playback import playback_lock
from VenomX.utils.playback_download import cached_playback
from random import randint
from typing import Union

from pyrogram.types import InlineKeyboardMarkup

import config
from VenomX import Platform, app, userbot
from VenomX.core.call import Ayush, MEDIA_ERRORS
from VenomX.misc import db
from VenomX.utils.database import (
    add_active_video_chat,
    get_vc_lyrics,
    get_assistant,
    is_video_allowed,
    get_instant_play,
)
from VenomX.utils.exceptions import AssistantErr
from VenomX.utils.formatters import time_to_seconds
from VenomX.utils.inline.playlist import close_markup
from VenomX.utils.pastebin import Ayushbin
from VenomX.utils.rich_msg import edit_any
from VenomX.utils.rich_panels import (
    notice_card,
    refresh_panel,
    replace_panel,
    spawn_now_playing,
)
from VenomX.utils.stream import lyrics as lyrics_display
from VenomX.utils.stream.queue import put_queue, put_queue_index
from VenomX.utils.thumbnails import gen_qthumb, gen_thumb
slog = logging.getLogger("VenomX.utils.stream.stream")


_PLAYBACK_SETUP_SECONDS = 100
_VIDEO_HEIGHTS = (144, 240, 360, 480, 720, 1080, 1440, 2160)


def _video_height() -> int:
    limit = getattr(config, "VIDEO_STREAM_LIMIT", 720) or 720
    allowed = [h for h in _VIDEO_HEIGHTS if h <= limit]
    return allowed[-1] if allowed else 360


_prefetch_tasks = {}


async def _start_lyrics(chat_id, title, duration, playback_started=None):
    """Show synced lyrics for the track that just started, posted by the assistant.

    Every path in stream() that joins the call calls this. Three of them did not,
    in three separate commits, each reported as "lyrics stopped working" — because
    a path that forgets to call this is indistinguishable, from the outside and
    from the log, from a lyrics endpoint that has broken.
    """
    try:
        if not await get_vc_lyrics(chat_id):
            return
    except Exception as e:
        slog.warning(
            "[%s] lyrics setting unreadable for %s: %s: %s",
            _STREAM_LOG, chat_id, type(e).__name__, e,
        )
        return
    seconds = None
    try:
        seconds = time_to_seconds(duration)
    except Exception:
        seconds = None
    try:
        assistant = await get_assistant(chat_id)
    except Exception:
        assistant = None
    if assistant is None:
        return
    use_title = getattr(config, "VC_LYRICS_TITLE", "True") in (True, "True", "true")
    post_message = getattr(config, "VC_LYRICS_MESSAGE", "False") in (True, "True", "true")

    async def _show():
        try:
            await lyrics_display.start(
                assistant, chat_id, title, seconds,
                post_message=post_message, use_title=use_title,
                playback_started=playback_started,
            )
        except Exception as e:
            slog.warning(
                "[%s] lyrics failed for %s: %s: %s",
                _STREAM_LOG, title[:40], type(e).__name__, e,
            )

    asyncio.create_task(_show())


def _prefetch_next(chat_id):
    """Warm the permalink for the next queued track while this one plays.

    Resolving takes ~4s; doing it now means the switch costs nothing.
    """
    queued = db.get(chat_id) or []
    if len(queued) < 2:
        return
    nxt = queued[1]
    vidid = nxt.get("vidid")
    if not vidid or vidid == "telegram":
        return
    video = nxt.get("streamtype") == "video"
    if _prefetch_tasks.get(chat_id) and not _prefetch_tasks[chat_id].done():
        return

    async def _warm():
        try:
            if await _api_stream_url(vidid, bool(video)):
                slog.info("[%s] prefetched permalink for next track %s", _STREAM_LOG, vidid)
        except Exception:
            pass

    _prefetch_tasks[chat_id] = asyncio.create_task(_warm())


async def _api_stream_url(vidid, video):
    """Check the response body before giving the permalink to a player."""
    params = {"type": "video", "height": _video_height()} if video else {}
    if config.VENOM_API_KEY:
        params["key"] = config.VENOM_API_KEY
    url = f"{_VENOM_API_URL.rstrip('/')}/stream/{vidid}"
    if params:
        url += "?" + urlencode(params)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=16)) as session:
            async with session.get(url, headers={"Range": "bytes=0-1023"}) as response:
                if (response.status in (200, 206)
                        and response.content_type.startswith(("audio/", "video/", "application/octet-stream"))
                        and await response.content.read(1)):
                    return url
                slog.warning("Media API probe failed for %s (HTTP %s)", vidid, response.status)
    except (aiohttp.ClientError, TimeoutError) as exc:
        slog.warning("Media API probe failed for %s (%s)", vidid, type(exc).__name__)
    return None


async def play_youtube_source(vidid, video, mystic, play, instant=True):
    """Try each source once. Only source errors should move playback to another source."""
    try:
        deadline = _time.monotonic() + _PLAYBACK_SETUP_SECONDS
        async with asyncio.timeout(_PLAYBACK_SETUP_SECONDS):
            return await _play_youtube_source(vidid, video, play, instant, deadline)
    except TimeoutError as exc:
        raise AssistantErr("Playback setup exceeded its deadline.") from exc


async def _play_youtube_source(vidid, video, play, instant, deadline):
    cached = await cached_playback(vidid, video)
    if cached:
        try:
            await play(cached)
            return cached
        except MEDIA_ERRORS as exc:
            slog.warning("Cached playback failed for %s (%s)", vidid, type(exc).__name__)

    if instant:
        try:
            permalink = await _api_stream_url(vidid, video)
        except Exception as exc:
            slog.warning("Media API lookup failed for %s (%s)", vidid, type(exc).__name__)
            permalink = None
        if permalink:
            try:
                await play(permalink)
                return permalink
            except MEDIA_ERRORS as exc:
                slog.warning("Media API playback failed for %s (%s)", vidid, type(exc).__name__)
        # Once playback starts the caller must immediately commit the queue and panel.
        # Start the fallback resolver only when this request actually needs it.
        try:
            ok, direct = await Platform.youtube.stream_url(vidid, videoid=True, video=video)
        except Exception as exc:
            slog.warning("Direct URL lookup failed for %s (%s)", vidid, type(exc).__name__)
            ok, direct = False, None
        if ok and direct:
            try:
                await play(direct)
                return direct
            except MEDIA_ERRORS as exc:
                slog.warning("Direct playback failed for %s (%s)", vidid, type(exc).__name__)
    try:
        path = await Platform.youtube.playback_file(vidid, video, _video_height(), deadline)
    except AssistantErr:
        raise
    except Exception as exc:
        raise AssistantErr(f"Could not download this track ({type(exc).__name__}).") from exc
    try:
        await play(path)
    except MEDIA_ERRORS as exc:
        raise AssistantErr(f"Could not play the downloaded media ({type(exc).__name__}).") from exc
    return path


_STREAM_LOG = "Stream"
_VENOM_API_URL = config.VENOM_API_URL


def _play_source_tag(stream_link) -> str | None:
    """Which pipe actually fuels this track — the card prints it "via".

    A media-API permalink (…/stream/<id>) means the Venom Api served the
    stream; anything else (googlevideo URL or a downloaded file) came through
    the bot's own yt-dlp. Telegram/soundcloud/saavn entries carry no tag here:
    the panel falls back to a file-prefix label for those.
    """
    if stream_link is None:
        return None
    return (
        "Venom Api"
        if str(stream_link).startswith(str(_VENOM_API_URL).rstrip("/"))
        else "YouTube"
    )


async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    admission = asyncio.timeout(15)
    try:
        async with admission:
            async with playback_lock(chat_id):
                admission.reschedule(None)
                return await _stream(_, mystic, user_id, result, chat_id, user_name,
                                     original_chat_id, video, streamtype, spotify, forceplay)
    except MEDIA_ERRORS as exc:
        if admission.expired():
            raise AssistantErr("Another playback operation is still running. Please try again.") from exc
        raise AssistantErr(f"Playback failed ({type(exc).__name__}).") from exc


async def _stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    st0 = _time.monotonic()
    slog.info(
        "[%s] stream() entry streamtype=%s chat=%s video=%s forceplay=%s result=%s",
        _STREAM_LOG, streamtype, chat_id, video, forceplay,
        str(result)[:80] if result else "None",
    )
    if not result:
        # A playlist that yields zero entries (Radio/Mix links cannot be
        # fetched) used to leave both the status card and the user hanging.
        if streamtype == "playlist":
            raise AssistantErr(_["playlist_26"])
        return
    if video:
        if not await is_video_allowed(chat_id):
            raise AssistantErr(_["play_7"])
    if forceplay:
        await Ayush.force_stop_stream(chat_id)
    if streamtype == "playlist":
        # A playlist is audio whatever the command was. /vplay used to carry a
        # video flag into every entry, so a playlist asked for as video queued
        # the whole list as video and the extra resolution bought nothing — the
        # person hears a track, not a picture.
        video = None
        msg = f"{_['playlist_16']}\n\n"
        count = 0
        started_track = False
        # Resolving one track to its video id takes the better part of a
        # second, and a playlist has hundreds of them: done one after another a
        # fifty-track list spends most of a minute in silence before the first
        # note. They are looked up together instead, a handful at a time so the
        # search backend is not hammered, and the results keep their order.
        entries = list(result)[: config.PLAYLIST_FETCH_LIMIT * 2]
        semaphore = asyncio.Semaphore(8)

        async def _resolve(search):
            async with semaphore:
                try:
                    return await Platform.youtube.details(
                        search, False if spotify else True
                    )
                except Exception:
                    return None

        slog.info("[%s] playlist: resolving %d entries", _STREAM_LOG, len(entries))
        _resolved = await asyncio.gather(*[_resolve(item) for item in entries])
        slog.info(
            "[%s] playlist: resolved %d/%d in %.1fs",
            _STREAM_LOG, len([r for r in _resolved if r]), len(entries),
            _time.monotonic() - st0,
        )
        for details in _resolved:
            if details is None:
                continue
            try:
                (
                    title,
                    duration_min,
                    duration_sec,
                    thumbnail,
                    vidid,
                ) = details
            except Exception:
                continue
            if str(duration_min) == "None":
                continue
            if duration_sec > config.DURATION_LIMIT:
                continue
            if await Ayush.is_live_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "audio",
                )
                _prefetch_next(chat_id)
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}- {title[:70]}\n"
                msg += f"{_['playlist_17']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                status = True if video else None
                instant = await get_instant_play(chat_id)
                stream_link = await play_youtube_source(
                    vidid, status, mystic,
                    partial(Ayush.join_call, chat_id, original_chat_id, video=status, image=thumbnail),
                    instant=instant,
                )
                # The playlist path joins the call but never told the lyrics
                # display anything, so a track started from a playlist produced no
                # lyrics at all — the same silence a broken endpoint produces, with
                # nothing in the log to tell the two apart.
                asyncio.create_task(
                    _start_lyrics(chat_id, title, duration_min)
                )
                slog.info("[%s] join_call done for vidid=%s", _STREAM_LOG, vidid)
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                    forceplay=forceplay,
                )
                try:
                    db[chat_id][0]["source"] = _play_source_tag(stream_link)
                except Exception:
                    pass
                started_track = True
                mid_np = await spawn_now_playing(
                    _, chat_id, vidid, title, duration_min, user_name,
                    thumb=thumbnail,
                )
                if not mid_np:
                    raise AssistantErr("Playback started, but Telegram could not send the player card.")
        if count == 0:
            if started_track:
                return
            # Radio/Mix playlists resolve to nothing — a silent return used to
            # leave the user staring at a dead status card with no feedback, so
            # surface the failure so the play handler shows an error card.
            raise AssistantErr(_["playlist_26"])
        else:
            link = await Ayushbin(msg)
            lines = msg.count("\n")
            if lines >= 17:
                car = os.linesep.join(msg.split(os.linesep)[:17])
            else:
                car = msg
            mid_np = await notice_card(
                _, original_chat_id, "ᴘʟᴀʏʟɪꜱᴛ ꜱᴜᴍᴍᴀʀʏ",
                _["playlist_18"].format(link, position),
            )
            return

    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]
        status = True if video else None
        if await Ayush.is_live_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            mid_np = await notice_card(
                _, original_chat_id, "Qᴜᴇᴜᴇ",
                _["queue_4"].format(position, title[:27], duration_min, user_name),
                thumb=await gen_qthumb(vidid),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            _jt = _time.monotonic()
            stream_link = await play_youtube_source(
                vidid, status, mystic,
                partial(Ayush.join_call, chat_id, original_chat_id, video=status, image=thumbnail),
                instant=await get_instant_play(chat_id),
            )
            asyncio.create_task(
                _start_lyrics(chat_id, title, duration_min,
                              playback_started=_time.monotonic())
            )
            _prefetch_next(chat_id)
            slog.info(
                "[%s] join_call took %.1fs (link_ready_age=%.1fs)",
                _STREAM_LOG, _time.monotonic() - _jt, _time.monotonic() - st0,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            try:
                db[chat_id][0]["source"] = _play_source_tag(stream_link)
            except Exception:
                pass
            mid_np = await spawn_now_playing(
                _, chat_id, vidid, title, duration_min, user_name,
                thumb=thumbnail,
            )
            if not mid_np:
                raise AssistantErr("Playback started, but Telegram could not send the player card.")
        slog.info("[%s] youtube branch completed in %.1fs for vidid=%s", _STREAM_LOG, _time.monotonic() - st0, vidid)

    elif "saavn" in streamtype:
        if streamtype == "saavn_track":
            if result["duration_sec"] == 0:
                return
            file_path = result["filepath"]
            title = result["title"]
            duration_min = result["duration_min"]
            link = result["url"]
            thumb = result["thumb"]
            if await Ayush.is_live_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path,
                    title,
                    duration_min,
                    user_name,
                    streamtype,
                    user_id,
                    "audio",
                    url=link,
                )
                position = len(db.get(chat_id)) - 1
                mid_np = await notice_card(
                    _, original_chat_id, "Qᴜᴇᴜᴇ",
                    _["queue_4"].format(position, title[:30], duration_min, user_name),
                    thumb=thumb,
                )
            else:
                if not forceplay:
                    db[chat_id] = []
                await Ayush.join_call(chat_id, original_chat_id, file_path, video=None)
                asyncio.create_task(
                    _start_lyrics(chat_id, title, duration_min)
                )
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path,
                    title,
                    duration_min,
                    user_name,
                    streamtype,
                    user_id,
                    "audio",
                    forceplay=forceplay,
                    url=link,
                )
                mid_np = await spawn_now_playing(
                    _, chat_id, None, title, duration_min, user_name,
                    thumb=thumb,
                )

        elif streamtype == "saavn_playlist":
            msg = f"{_['playlist_16']}\n\n"
            count = 0
            for search in result:
                if search["duration_sec"] == 0:
                    continue
                title = search["title"]
                duration_min = search["duration_min"]
                duration_sec = search["duration_sec"]
                link = search["url"]
                thumb = search["thumb"]
                file_path, details = await Platform.saavn.download(link)
                if await Ayush.is_live_chat(chat_id):
                    await put_queue(
                        chat_id,
                        original_chat_id,
                        file_path,
                        title,
                        duration_min,
                        user_name,
                        streamtype,
                        user_id,
                        "audio",
                        url=link,
                    )
                    position = len(db.get(chat_id)) - 1
                    count += 1
                    msg += f"{count}- {title[:70]}\n"
                    msg += f"{_['playlist_17']} {position}\n\n"

                else:

                    if not forceplay:
                        db[chat_id] = []
                    await Ayush.join_call(
                        chat_id, original_chat_id, file_path, video=None
                    )
                    asyncio.create_task(
                        _start_lyrics(chat_id, title, duration_min)
                    )
                    await put_queue(
                        chat_id,
                        original_chat_id,
                        file_path,
                        title,
                        duration_min,
                        user_name,
                        streamtype,
                        user_id,
                        "audio",
                        forceplay=forceplay,
                        url=link,
                    )
                    mid_np = await spawn_now_playing(
                        _, chat_id, None, title, duration_min, user_name,
                        thumb=thumb,
                    )
            if count == 0:
                return
            else:
                link = await Ayushbin(msg)
                lines = msg.count("\n")
                if lines >= 17:
                    car = os.linesep.join(msg.split(os.linesep)[:17])
                else:
                    car = msg
                mid_np = await notice_card(
                    _, original_chat_id, "ᴘʟᴀʏʟɪꜱᴛ ꜱᴜᴍᴍᴀʀʏ",
                    _["playlist_18"].format(link, position),
                )
                return

    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]
        if await Ayush.is_live_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            position = len(db.get(chat_id)) - 1
            await notice_card(
                _,
                original_chat_id,
                "Qᴜᴇᴜᴇ",
                _["queue_4"].format(position, title[:30], duration_min, user_name),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Ayush.join_call(chat_id, original_chat_id, file_path, video=None)
            asyncio.create_task(_start_lyrics(chat_id, title, duration_min))
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            mid_np = await spawn_now_playing(
                _, chat_id, None, title, duration_min, user_name,
                thumb=config.SOUNCLOUD_IMG_URL,
            )
    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        status = True if video else None
        if await Ayush.is_live_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            await notice_card(
                _,
                original_chat_id,
                "Qᴜᴇᴜᴇ",
                _["queue_4"].format(position, title[:30], duration_min, user_name),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Ayush.join_call(chat_id, original_chat_id, file_path, video=status)
            asyncio.create_task(_start_lyrics(chat_id, title, duration_min))
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            if video:
                await add_active_video_chat(chat_id)
            mid_np = await spawn_now_playing(
                _, chat_id, None, title, duration_min, user_name,
                thumb=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL,
            )
    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        thumbnail = result["thumb"]
        duration_min = "00:00"
        status = True if video else None
        if await Ayush.is_live_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            await notice_card(
                _,
                original_chat_id,
                "Qᴜᴇᴜᴇ",
                _["queue_4"].format(position, title[:30], duration_min, user_name),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            slog.info("[%s] live branch: calling video() for link=%s", _STREAM_LOG, link[:80])
            n, file_path = await Platform.youtube.video(link)
            slog.info("[%s] video() returned n=%s", _STREAM_LOG, n)
            if n == 0:
                raise AssistantErr(_["str_3"])
            await Ayush.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=thumbnail if thumbnail else None,
            )
            asyncio.create_task(_start_lyrics(chat_id, title, duration_min))
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            img = await gen_thumb(vidid)
            mid_np = await spawn_now_playing(
                _, chat_id, vidid, title, duration_min, user_name,
                thumb=img,
            )
    elif streamtype == "index":
        link = result
        title = "Index or M3u8 Link"
        duration_min = "URL stream"
        if await Ayush.is_live_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            await edit_any(
                mystic,
                _["queue_4"].format(position, title[:30], duration_min, user_name),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Ayush.join_call(
                chat_id,
                original_chat_id,
                link,
                video=True if video else None,
            )
            asyncio.create_task(_start_lyrics(chat_id, title, duration_min))
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            mid_np = await spawn_now_playing(
                _, chat_id, None, title, duration_min, user_name,
                thumb=config.STREAM_IMG_URL,
            )
            await mystic.delete()
