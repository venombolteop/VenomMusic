
# All rights reserved.
#

import asyncio
import logging
import os
import time as _time
from random import randint
from typing import Union

import aiohttp
from pyrogram.types import InlineKeyboardMarkup

import config
from VenomX import Platform, app, userbot
from VenomX.core.call import Ayush
from VenomX.misc import db
from VenomX.utils.database import (
    add_active_video_chat,
    is_active_chat,
    is_video_allowed,
    get_instant_play,
)
from VenomX.utils.exceptions import AssistantErr
from VenomX.utils.formatters import time_to_seconds
from VenomX.utils.inline.play import stream_markup, telegram_markup
from VenomX.utils.inline.playlist import close_markup
from VenomX.utils.pastebin import Ayushbin
from VenomX.utils.stream import lyrics as lyrics_display
from VenomX.utils.stream.queue import put_queue, put_queue_index
from VenomX.utils.thumbnails import gen_qthumb, gen_thumb
from VenomX.utils.notify import notify_owner
slog = logging.getLogger("VenomX.utils.stream.stream")


_VIDEO_HEIGHTS = (144, 240, 360, 480, 720, 1080, 1440, 2160)


def _video_height() -> int:
    limit = getattr(config, "VIDEO_STREAM_LIMIT", 720) or 720
    allowed = [h for h in _VIDEO_HEIGHTS if h <= limit]
    return allowed[-1] if allowed else 360


_prefetch_tasks = {}
# The media API permalink is stable and never expires, so it is safe to keep.
_permalink_cache = {}


def _cached_permalink(vidid, video):
    return _permalink_cache.get((vidid, bool(video)))


def _remember_permalink(vidid, video, url):
    if url:
        _permalink_cache[(vidid, bool(video))] = url
        if len(_permalink_cache) > 512:
            _permalink_cache.pop(next(iter(_permalink_cache)))


def _start_lyrics(chat_id, title, duration):
    """Show synced lyrics for the track that just started, posted by the assistant."""
    if not getattr(config, "VC_LYRICS", "False") in (True, "True", "true"):
        return
    seconds = None
    try:
        seconds = time_to_seconds(duration)
    except Exception:
        seconds = None
    try:
        assistant = userbot.clients[0]
    except Exception:
        assistant = None
    if assistant is None:
        return
    async def _show():
        try:
            await lyrics_display.start(assistant, chat_id, title, seconds)
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
            await _api_stream_url(vidid, bool(video))
            slog.info("[%s] prefetched permalink for next track %s", _STREAM_LOG, vidid)
        except Exception:
            pass

    _prefetch_tasks[chat_id] = asyncio.create_task(_warm())


async def _api_stream_url(vidid, video):
    """Resolve a playable permalink through the local media API.

    Returns None when the API is unreachable or the id cannot be resolved, so
    the caller keeps its existing download path.
    """
    cached = _cached_permalink(vidid, video)
    if cached:
        slog.info("[%s] permalink cache hit for %s", _STREAM_LOG, vidid)
        return cached

    # The API's permalink is always /stream/<id>, so build it here instead of
    # asking: /v1/link spends ~4s extracting metadata only to return a title we
    # already have. A short ranged GET proves the id is servable.
    local_url = f"{_VENOM_API_URL.rstrip('/')}/stream/{vidid}"
    if video:
        local_url += f"?type=video&height={_video_height()}"
    # Checking it inline would mean waiting for the first bytes, and on a track
    # the API has never fetched that is the whole cold-start cost — exactly the
    # delay this path exists to remove. Hand the URL over and verify behind the
    # playback instead.
    _remember_permalink(vidid, video, local_url)
    return local_url

_STREAM_LOG = "Stream"

_PROXY_URL = getattr(config, "PROXY_URL", None)
# GoogleVideo direct URLs are bound to the proxy exit IP (which WARP rotates),
# so they 403 at playback time. The media API hands back a stable permalink on
# this box instead, which streams instantly. Falls back to download when absent.
_VENOM_API_URL = getattr(config, "VENOM_API_URL", "http://127.0.0.1:3200")
_FORCE_DOWNLOAD = False


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
    st0 = _time.monotonic()
    slog.info(
        "[%s] stream() entry streamtype=%s chat=%s video=%s forceplay=%s result=%s",
        _STREAM_LOG, streamtype, chat_id, video, forceplay,
        str(result)[:80] if result else "None",
    )
    if not result:
        return
    if video:
        if not await is_video_allowed(chat_id):
            raise AssistantErr(_["play_7"])
    if forceplay:
        await Ayush.force_stop_stream(chat_id)
    if streamtype == "playlist":
        msg = f"{_['playlist_16']}\n\n"
        count = 0
        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                (
                    title,
                    duration_min,
                    duration_sec,
                    thumbnail,
                    vidid,
                ) = await Platform.youtube.details(search, False if spotify else True)
            except Exception:
                continue
            if str(duration_min) == "None":
                continue
            if duration_sec > config.DURATION_LIMIT:
                continue
            if await is_active_chat(chat_id):
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
                slog.info(
                    "[%s] playlist first-track: vidid=%s instant=%s",
                    _STREAM_LOG, vidid, instant,
                )
                if instant:
                    n = 0
                    stream_link = await _api_stream_url(vidid, bool(status))
                    if stream_link:
                        n = 1
                        direct = True
                        slog.info(
                            "[%s] playlist first-track permalink %s", _STREAM_LOG, vidid
                        )
                    else:
                        try:
                            n, stream_link = await Platform.youtube.stream_url(
                                vidid, videoid=True, video=status
                            )
                            slog.info("[%s] playlist stream_url() returned n=%s", _STREAM_LOG, n)
                        except Exception as e:
                            slog.error("[%s] playlist stream_url() EXCEPTION: %s", _STREAM_LOG, e)
                    if n == 0:
                        try:
                            stream_link, direct = await Platform.youtube.download(
                                vidid, mystic, video=status, videoid=True
                            )
                        except Exception as e:
                            try:
                                await notify_owner(
                                    "Stream.playlist.download(fallback)",
                                    e,
                                    f"vidid={vidid} chat={chat_id}",
                                )
                            except Exception:
                                pass
                            raise AssistantErr(_["play_16"])
                    else:
                        direct = True
                else:
                    try:
                        stream_link, direct = await Platform.youtube.download(
                            vidid, mystic, video=status, videoid=True
                        )
                    except Exception as e:
                        try:
                            await notify_owner(
                                "Stream.playlist.download",
                                e,
                                f"vidid={vidid} chat={chat_id}",
                            )
                        except Exception:
                            pass
                        raise AssistantErr(_["play_16"])
                await Ayush.join_call(
                    chat_id, original_chat_id, stream_link, video=status, image=thumbnail
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
                img = await gen_thumb(vidid)
                button = stream_markup(_, vidid, chat_id)
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        title[:27],
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        if count == 0:
            return
        else:
            link = await Ayushbin(msg)
            lines = msg.count("\n")
            if lines >= 17:
                car = os.linesep.join(msg.split(os.linesep)[:17])
            else:
                car = msg
            carbon = await Platform.carbon.generate(car, randint(100, 10000000))
            upl = close_markup(_)
            return await app.send_photo(
                original_chat_id,
                photo=carbon,
                caption=_["playlist_18"].format(link, position),
                reply_markup=upl,
            )

    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]
        status = True if video else None
        instant = await get_instant_play(chat_id)
        # Force download when proxy is configured (ffmpeg proxy issues cause no sound)
        if _FORCE_DOWNLOAD:
            instant = False
        slog.info(
            "[%s] youtube branch: vidid=%s title=%s instant=%s (force_download=%s) age=%.1fs",
            _STREAM_LOG, vidid, title[:40], instant, _FORCE_DOWNLOAD, _time.monotonic() - st0,
        )
        stream_link = None
        direct = None
        if instant:
            _warm = asyncio.create_task(
                Ayush.warm_join(chat_id)
            ) if not getattr(config, "SEQUENTIAL_WARMUP", False) else None
            api_url = await _api_stream_url(vidid, bool(status))
            if _warm is not None:
                _warm.cancel()
            if api_url:
                slog.info(
                    "[%s] media API permalink ready for vidid=%s video=%s in %.1fs",
                    _STREAM_LOG, vidid, bool(status), _time.monotonic() - st0,
                )
                stream_link = api_url
                direct = True
            else:
                n = 0
                try:
                    n, stream_link = await Platform.youtube.stream_url(
                        vidid, videoid=True, video=status
                    )
                    slog.info("[%s] stream_url() returned n=%s", _STREAM_LOG, n)
                except Exception as e:
                    slog.error("[%s] stream_url() EXCEPTION: %s", _STREAM_LOG, e)
                    n = 0
                if n != 0 and stream_link:
                    direct = True
                else:
                    n = 0
            if not direct:
                try:
                    slog.info("[%s] instant path unavailable, fallback download()...", _STREAM_LOG)
                    stream_link, direct = await Platform.youtube.download(
                        vidid, mystic, videoid=True, video=status
                    )
                    slog.info("[%s] download() returned direct=%s", _STREAM_LOG, direct)
                except Exception as e:
                    slog.error("[%s] download() EXCEPTION: %s", _STREAM_LOG, e)
                    try:
                        await notify_owner(
                            "Stream.youtube.download(fallback)",
                            e,
                            f"vidid={vidid} chat={chat_id}",
                        )
                    except Exception:
                        pass
                    raise AssistantErr(_["play_16"])
        else:
            try:
                slog.info("[%s] instant OFF, downloading...", _STREAM_LOG)
                stream_link, direct = await Platform.youtube.download(
                    vidid, mystic, videoid=True, video=status
                )
                slog.info("[%s] download() returned direct=%s", _STREAM_LOG, direct)
            except Exception as e:
                slog.error("[%s] download() EXCEPTION: %s", _STREAM_LOG, e)
                try:
                    await notify_owner(
                        "Stream.youtube.download",
                        e,
                        f"vidid={vidid} chat={chat_id}",
                    )
                except Exception:
                    pass
                raise AssistantErr(_["play_16"])
        if await is_active_chat(chat_id):
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
            qimg = await gen_qthumb(vidid)
            run = await app.send_photo(
                original_chat_id,
                photo=qimg,
                caption=_["queue_4"].format(
                    position, title[:27], duration_min, user_name
                ),
                reply_markup=close_markup(_),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            _jt = _time.monotonic()
            await Ayush.join_call(
                chat_id, original_chat_id, stream_link, video=status, image=thumbnail
            )
            _start_lyrics(chat_id, title, duration_min)
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
            img = await gen_thumb(vidid)
            button = stream_markup(_, vidid, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    title[:27],
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
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
            if await is_active_chat(chat_id):
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
                await app.send_photo(
                    original_chat_id,
                    photo=thumb or "https://envs.sh/Ii_.jpg",
                    caption=_["queue_4"].format(
                        position, title[:30], duration_min, user_name
                    ),
                    reply_markup=close_markup(_),
                )
            else:
                if not forceplay:
                    db[chat_id] = []
                await Ayush.join_call(chat_id, original_chat_id, file_path, video=None)
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
                button = telegram_markup(_, chat_id)
                run = await app.send_photo(
                    original_chat_id,
                    photo=thumb,
                    caption=_["stream_1"].format(
                        title, config.SUPPORT_GROUP, duration_min, user_name
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

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
                file_path, n = await Platform.saavn.download(link)
                if await is_active_chat(chat_id):
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
                    button = telegram_markup(_, chat_id)
                    run = await app.send_photo(
                        original_chat_id,
                        photo=thumb,
                        caption=_["stream_1"].format(
                            title, link, duration_min, user_name
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
            if count == 0:
                return
            else:
                link = await Ayushbin(msg)
                lines = msg.count("\n")
                if lines >= 17:
                    car = os.linesep.join(msg.split(os.linesep)[:17])
                else:
                    car = msg
                carbon = await Platform.carbon.generate(car, randint(100, 10000000))
                upl = close_markup(_)
                return await app.send_photo(
                    original_chat_id,
                    photo=carbon,
                    caption=_["playlist_18"].format(link, position),
                    reply_markup=upl,
                )

    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]
        if await is_active_chat(chat_id):
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
            await app.send_message(
                original_chat_id,
                _["queue_4"].format(position, title[:30], duration_min, user_name),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Ayush.join_call(chat_id, original_chat_id, file_path, video=None)
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
            button = telegram_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=_["stream_1"].format(
                    title, config.SUPPORT_GROUP, duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        status = True if video else None
        if await is_active_chat(chat_id):
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
            await app.send_message(
                original_chat_id,
                _["queue_4"].format(position, title[:30], duration_min, user_name),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Ayush.join_call(chat_id, original_chat_id, file_path, video=status)
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
            button = telegram_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL,
                caption=_["stream_1"].format(title, link, duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        thumbnail = result["thumb"]
        duration_min = "00:00"
        status = True if video else None
        if await is_active_chat(chat_id):
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
            await app.send_message(
                original_chat_id,
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
            button = telegram_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    title[:27],
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
    elif streamtype == "index":
        link = result
        title = "Index or M3u8 Link"
        duration_min = "URL stream"
        if await is_active_chat(chat_id):
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
            await mystic.edit_text(
                _["queue_4"].format(position, title[:30], duration_min, user_name)
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
            button = telegram_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await mystic.delete()
