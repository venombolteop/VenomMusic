
# All rights reserved.
#
# Song download module — rich-message panels (Bot API 10.3) + Venom branding.
#

import os
import re

import aiohttp
import yt_dlp
from pyrogram import enums, filters
from pyrogram.types import Message

import config
from config import (
    BANNED_USERS,
    PROXY_URL,
    SONG_DOWNLOAD_DURATION,
    SONG_DOWNLOAD_DURATION_LIMIT,
)
from strings import command
from VenomX import Platform, app
from VenomX.utils.decorators.language import language, languageCB
from VenomX.utils.formatters import convert_bytes
from VenomX.utils.inline.song import song_markup
from VenomX.utils.rich_msg import (
    delete_msg,
    edit_rich,
    pemoji,
    rich_button,
    rich_button_row,
    rich_esc,
    rich_heading,
    rich_img,
    send_audio,
    send_rich,
    send_video,
)


def song_panel_html(_, thumbnail, title, vidid):
    body = rich_img(thumbnail)
    body += rich_heading(f'{pemoji("🎧")} ᴠᴇɴᴏᴍ sᴏɴɢ ᴅᴏᴡɴʟᴏᴀᴅ', level=4)
    body += f"<p>{rich_esc(_['song_4'].format(title))}</p>"
    body += song_markup(_, vidid)
    return body


def formats_panel_html(rows, back_html):
    body = rich_heading(f'{pemoji("🗂")} ǫᴜᴀʟɪᴛʏ ᴘɪᴄᴋ', level=4)
    body += "".join(rows)
    body += back_html
    return body


@app.on_message(command("SONG_COMMAND") & filters.group & ~BANNED_USERS)
@language
async def song_commad_group(client, message: Message, _):
    body = (
        f"<p>{rich_esc(_['song_1'])}</p>"
        + rich_button_row(
            f'<tg-button type="url" style="primary" '
            f'url="https://t.me/{app.username}?start=song">'
            f'{pemoji("🔗")} ᴏᴘᴇɴ Dᴍ</tg-button>'
        )
    )
    await send_rich(message.chat.id, body)


@app.on_message(command("SONG_COMMAND") & filters.private & ~BANNED_USERS)
@language
async def song_commad_private(client, message: Message, _):
    await message.delete()

    url = await Platform.youtube.url(message)

    if url:

        if not await Platform.youtube.exists(url):
            return await send_rich(
                message.chat.id, f"<p>{rich_esc(_['song_5'])}</p>"
            )

        (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        ) = await Platform.youtube.details(url)

        if str(duration_min) == "None":
            return await send_rich(
                message.chat.id, f"<p>{rich_esc(_['song_3'])}</p>"
            )

        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await send_rich(
                message.chat.id,
                f"<p>{rich_esc(_['play_4'].format(SONG_DOWNLOAD_DURATION, duration_min))}</p>",
            )

        return await send_rich(
            message.chat.id, song_panel_html(_, thumbnail, title, vidid)
        )

    else:

        if len(message.command) < 2:
            return await send_rich(
                message.chat.id, f"<p>{rich_esc(_['song_2'])}</p>"
            )

    query = message.command[1]

    try:
        (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        ) = await Platform.youtube.details(query)
    except Exception:
        return await send_rich(
            message.chat.id, f"<p>{rich_esc(_['play_3'])}</p>"
        )

    if str(duration_min) == "None":
        return await send_rich(
            message.chat.id, f"<p>{rich_esc(_['song_3'])}</p>"
        )

    if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
        return await send_rich(
            message.chat.id,
            f"<p>{rich_esc(_['play_6'].format(SONG_DOWNLOAD_DURATION, duration_min))}</p>",
        )

    return await send_rich(
        message.chat.id, song_panel_html(_, thumbnail, title, vidid)
    )


@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
@languageCB
async def songs_back_helper(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    stype, vidid = callback_request.split("|")
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    chat_id = CallbackQuery.message.chat.id
    mid = CallbackQuery.message.id
    try:
        thumbnail = CallbackQuery.message.photo.file_id
    except Exception:
        thumbnail = config_placeholder_thumb()
    await edit_rich(chat_id, mid, song_panel_html(_, thumbnail, "", vidid))


def config_placeholder_thumb():
    return "https://i.ibb.co/7zYzRJw/a8800c683dee8d9919d24dbdde5eed6a-1.jpg"


def _api_audio_url():
    return (getattr(config, "VENOM_API_URL", "") or "").strip()


async def _api_audio_download(
    chat_id: int, mid: int, vidid: str, title: str, format_id=None
):
    """MP3 fast path through the media server's /v1/download.

    The server plays from its warm cache when it can, so a popular track
    arrives without touching YouTube at all. Returns the written file path,
    or None when the API is unreachable or refuses the request — the caller
    then renders the whole file with yt-dlp exactly as before.
    """
    import logging

    url = _api_audio_url()
    if not url:
        return None
    headers = {"accept": "application/octet-stream"}
    if getattr(config, "VENOM_API_KEY", ""):
        headers["x-api-key"] = config.VENOM_API_KEY
    payload = {
        "url": f"https://www.youtube.com/watch?v={vidid}",
        "type": "audio",
        "convert": "mp3",
    }
    if str(format_id) == "320":
        # The picker's highest-audio choice: the API holds the mp3 transcode
        # at CBR 320 kbps (its default is the encoder ceiling VBR, ~245 kbps).
        payload["abr"] = 320
    os.makedirs("downloads", exist_ok=True)
    safe = re.sub(r"\W+", " ", title).strip().replace(" ", "_")[:60] or vidid
    dest = os.path.join("downloads", f"{vidid}_{safe}.mp3")
    try:
        timeout = aiohttp.ClientTimeout(total=280)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url.rstrip("/") + "/v1/download",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    logging.getLogger("VenomX.plugins.tools.songs").debug(
                        "API download answered %d; falling back to yt-dlp",
                        resp.status,
                    )
                    return None
                written = 0
                with open(dest, "wb") as _fh:
                    async for chunk in resp.content.iter_chunked(65536):
                        _fh.write(chunk)
                        written += len(chunk)
        if written < 1024:
            os.remove(dest)
            return None
        logging.getLogger("VenomX.plugins.tools.songs").info(
            "API audio download: %d bytes from warm cache (%s)", written, vidid
        )
        return dest
    except Exception:
        logging.getLogger("VenomX.plugins.tools.songs").warning(
            "API audio download failed for %s; falling back to yt-dlp", vidid,
            exc_info=True,
        )
        try:
            os.remove(dest)
        except OSError:
            pass
        return None


@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
@languageCB
async def song_helper_cb(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    stype, vidid = callback_request.split("|")

    try:
        await CallbackQuery.answer(_["song_6"], show_alert=True)
    except Exception:
        pass

    back_html = rich_button_row(
        rich_button(
            f"{pemoji('🚀')} {_['BACK_BUTTON']}",
            callback_data=f"song_back {stype}|{vidid}",
            style="primary",
        ),
        rich_button(
            f"{pemoji('❌')} {_['CLOSE_BUTTON']}",
            callback_data="close",
            style="danger",
        ),
    )

    try:
        formats_available, link = await Platform.youtube.formats(vidid, True)
    except Exception:
        return await edit_rich(
            CallbackQuery.message.chat.id,
            CallbackQuery.message.id,
            f"<p>{rich_esc(_['song_7'])}</p>",
        )

    rows = []

    if stype == "audio":
        rows.append(
            rich_button_row(
                rich_button(
                    f"{pemoji('🎧')} 320 KBPS MP3 (Best)",
                    callback_data=f"song_download {stype}|320|{vidid}",
                    style="primary",
                )
            )
        )
        done = []
        for x in formats_available:
            check = x["format"]
            if "audio" in check:
                if x["filesize"] is None:
                    continue
                form = x["format_note"].title()
                if form not in done:
                    done.append(form)
                else:
                    continue
                sz = convert_bytes(x["filesize"])
                fom = x["format_id"]
                rows.append(
                    rich_button_row(
                        rich_button(
                            f"{pemoji('🎵')} {form} = {sz}",
                            callback_data=f"song_download {stype}|{fom}|{vidid}",
                            style="primary",
                        )
                    )
                )
    else:
        # Highest resolution first, deduped per height. The format-note (e.g.
        # "1080p60") is the only reliable resolution hint, and YouTube's
        # ladder often exposes several formats at one height — keep the
        # largest file. The old hardcoded itag whitelist hid whatever the
        # extractor's current clients didn't emit, which is why 2K/4K/8K
        # never showed up.
        by_height: dict[int, dict] = {}
        for x in formats_available:
            if x["filesize"] is None:
                continue
            note = (x["format_note"] or "").lower()
            fmt = str(x["format"]).lower()
            m = re.search(r"(\d{3,4})p", note) or re.search(r"(\d{3,4})p", fmt)
            if not m:
                continue
            height = int(m.group(1))
            cur = by_height.get(height)
            if cur is None or (x["filesize"] or 0) > (cur["filesize"] or 0):
                by_height[height] = x
        for height in sorted(by_height, reverse=True)[:10]:
            x = by_height[height]
            sz = convert_bytes(x["filesize"])
            rows.append(
                rich_button_row(
                    rich_button(
                        f"{pemoji('🎥')} {height}p = {sz}",
                        callback_data=f"song_download {stype}|{x['format_id']}|{vidid}",
                        style="primary",
                    )
                )
            )

    await edit_rich(
        CallbackQuery.message.chat.id,
        CallbackQuery.message.id,
        formats_panel_html(rows, back_html),
    )


@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
@languageCB
async def song_download_cb(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer("ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ...")
    except Exception:
        pass

    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    stype, format_id, vidid = callback_request.split("|")

    chat_id = CallbackQuery.message.chat.id
    mid = CallbackQuery.message.id

    await edit_rich(chat_id, mid, f"<p>{rich_esc(_['song_8'])}</p>")

    yturl = f"https://www.youtube.com/watch?v={vidid}"

    import asyncio as _aio

    async def _api_meta():
        """(title, duration, uploader) from the local media API, None on miss."""
        url = (getattr(config, "VENOM_API_URL", "") or "").strip()
        if not url:
            return None
        try:
            _headers = {"accept": "application/json"}
            _key = (getattr(config, "VENOM_API_KEY", "") or "").strip()
            if _key:
                _headers["x-api-key"] = _key
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                async with session.post(
                    f"{url.rstrip('/')}/v1/resolve",
                    json={"url": yturl},
                    headers=_headers,
                ) as resp:
                    if resp.status != 200:
                        return None
                    payload = await resp.json()
        except Exception as e:
            import logging as _logging

            _logging.getLogger("Song").debug("meta via API failed: %s: %s", type(e).__name__, e)
            return None
        if not payload.get("title"):
            return None
        return (
            payload["title"],
            payload.get("duration"),
            payload.get("uploader") or "Venom Music",
        )

    meta = await _api_meta()
    if meta:
        title, duration, uploader = meta
    else:
        # Fallback: blocking extract in an executor thread so the bot's loop
        # is not held up while the API is down.
        def _ytdl_meta():
            _ytdl_opts = {
                "quiet": True,
                "extractor_args": {"youtube": {"client": ["web_creator"]}},
                "remote_components": ["ejs:github"],
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            }
            if PROXY_URL:
                _ytdl_opts["proxy"] = PROXY_URL
            _ytdl_opts["cookiefile"] = None
            from VenomX.platforms.Youtube import cookies

            cp = cookies()
            if cp:
                _ytdl_opts["cookiefile"] = cp
            with yt_dlp.YoutubeDL(_ytdl_opts) as ytdl:
                x = ytdl.extract_info(yturl, download=False)
            return (
                (x["title"]).title(),
                x["duration"],
                x.get("uploader") or "Venom Music",
            )

        title, duration, uploader = await _aio.get_running_loop().run_in_executor(
            None, _ytdl_meta
        )
    title = re.sub(r"\W+", " ", title)

    try:
        await edit_rich(chat_id, mid, f"<p>{rich_esc(_['song_11'])}</p>")
        await app.send_chat_action(
            chat_id=chat_id, action=enums.ChatAction.UPLOAD_VIDEO
        )

        file_path = None
        if stype == "audio":
            # The media API usually has popular tracks on a warm disk cache,
            # so its /v1/download is faster than a local yt-dlp run. Any
            # failure falls through to the local path below.
            file_path = await _api_audio_download(
                chat_id, mid, vidid, title, format_id
            )
        if file_path is None:
            if stype == "video":
                file_path = await Platform.youtube.download(
                    yturl,
                    None,
                    songvideo=True,
                    format_id=format_id,
                    title=title,
                )
            else:
                file_path = await Platform.youtube.download(
                    yturl,
                    None,
                    songaudio=True,
                    format_id=format_id,
                    title=title,
                )
    except Exception as e:
        return await edit_rich(chat_id, mid, f"<p>{rich_esc(_['song_9'].format(e))}</p>")

    if stype == "video":
        try:
            await send_video(
                chat_id,
                file_path,
                caption=title,
                duration=duration,
                streaming=True,
            )
            await delete_msg(chat_id, mid)
        except Exception:
            await edit_rich(chat_id, mid, f"<p>{rich_esc(_['song_10'])}</p>")
        os.remove(file_path)
    elif stype == "audio":
        try:
            await send_audio(
                chat_id,
                file_path,
                caption=title,
                title=title,
                performer=uploader,
            )
            await delete_msg(chat_id, mid)
        except Exception:
            await edit_rich(chat_id, mid, f"<p>{rich_esc(_['song_10'])}</p>")
        os.remove(file_path)
