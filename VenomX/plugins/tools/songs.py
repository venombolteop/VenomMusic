
# All rights reserved.
#
# Song download module — rich-message panels (Bot API 10.3) + Venom branding.
#

import os
import re

import yt_dlp
from pyrogram import enums, filters
from pyrogram.types import Message

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
        done = [160, 133, 134, 135, 136, 137, 298, 299, 264, 304, 266]
        for x in formats_available:
            check = x["format"]
            if x["filesize"] is None:
                continue
            if int(x["format_id"]) not in done:
                continue
            sz = convert_bytes(x["filesize"])
            ap = check.split("-", 1)[-1] if "-" in check else check
            rows.append(
                rich_button_row(
                    rich_button(
                        f"{pemoji('🎥')} {ap} = {sz}",
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

    with yt_dlp.YoutubeDL(_ytdl_opts) as ytdl:
        x = ytdl.extract_info(yturl, download=False)

    title = (x["title"]).title()
    title = re.sub(r"\W+", " ", title)

    duration = x["duration"]

    try:
        await edit_rich(chat_id, mid, f"<p>{rich_esc(_['song_11'])}</p>")
        await app.send_chat_action(
            chat_id=chat_id, action=enums.ChatAction.UPLOAD_VIDEO
        )

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
        j = await send_video(
            chat_id,
            file_path,
            caption=title,
            duration=duration,
            streaming=True,
        )
        if j.get("ok"):
            await delete_msg(chat_id, mid)
        else:
            await edit_rich(chat_id, mid, f"<p>{rich_esc(_['song_10'])}</p>")
        os.remove(file_path)
    elif stype == "audio":
        j = await send_audio(
            chat_id,
            file_path,
            caption=title,
            title=title,
            performer=x["uploader"],
        )
        if j.get("ok"):
            await delete_msg(chat_id, mid)
        else:
            await edit_rich(chat_id, mid, f"<p>{rich_esc(_['song_10'])}</p>")
        os.remove(file_path)
