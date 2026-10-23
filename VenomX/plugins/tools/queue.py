
# All rights reserved.
#
# Queue tool — fully rich-message (Bot API 10.3) with Venom Music branding.
#

import asyncio

from pyrogram import filters
from pyrogram.types import CallbackQuery, Message

import config
from config import BANNED_USERS
from strings import command
from VenomX import app, Platform
from VenomX.misc import db
from VenomX.utils import Ayushbin, get_channeplayCB, seconds_to_min
from VenomX.utils.database import get_cmode, is_active_chat, is_music_playing
from VenomX.utils.decorators import ActualAdminCB
from VenomX.utils.decorators.language import language, languageCB
from VenomX.utils.inline.queue import queue_back_markup, queue_markup
from VenomX.utils.rich_msg import (
    edit_rich,
    pemoji,
    rich_button,
    rich_button_row,
    rich_esc,
    rich_heading,
    rich_img,
    send_rich,
)

basic = {}


def get_image(videoid):
    try:
        return f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"
    except Exception:
        return config.YOUTUBE_IMG_URL


def get_duration(playing):
    file_path = playing[0]["file"]
    if "index_" in file_path or "live_" in file_path:
        return "Unknown"
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return "Unknown"
    return "Inline"


def player_html(_, image, title, stream_type, user, run_info, cplay, videoid):
    body = rich_img(image)
    body += rich_heading(f'{pemoji("🎧")} ᴠᴇɴᴏᴍ ᴍᴜsɪᴄ ᴘʟᴀʏᴇʀ', level=4)
    body += f"<p>{pemoji('🎼')} ᴘʟᴀʏɪɴɢ : <b>{rich_esc(title)}</b></p>"
    body += f"<p>{pemoji('🔊')} sᴛʀᴇᴀᴍ : {rich_esc(stream_type)}</p>"
    body += f"<p>{pemoji('👤')} ᴘʟᴀʏᴇᴅ ʙʏ : <b>{rich_esc(user)}</b></p>"
    if run_info is None:
        body += f"<p>{pemoji('⏳')} ᴅᴜʀᴀᴛɪᴏɴ : ᴜɴᴋɴᴏᴡɴ</p>"
        body += f"<p>{pemoji('🗂')} ᴛᴀᴘ ᴏᴜᴛᴘᴜᴛ ᴛᴏ ᴠɪᴇᴡ ᴛʜᴇ ᴡʜᴏʟᴇ ǫᴜᴇᴜᴇ</p>"
        body += queue_markup(_, "Unknown", cplay, videoid)
    else:
        played, dur = run_info
        body += f"<p>{pemoji('⏱')} ᴛɪᴍᴇʀ : <b>{rich_esc(played)}</b> / {rich_esc(dur)}</p>"
        body += queue_markup(_, "Inline", cplay, videoid, played, dur)
    return body


def plain_list_text(got):
    j = 0
    msg = ""
    for x in got:
        j += 1
        if j == 1:
            msg += (
                f'🔴 {x["title"]}\n⏱ {x["dur"]}\n🎙 {x["by"]}\n\n'
                "➡️ ᴜᴘ ɴᴇxᴛ ʜᴇʀᴇ ᴅᴇᴀᴅʀᴇɴ:\n\n"
            )
        else:
            msg += f'{j}. {x["title"]}\n⏱ {x["dur"]}\n🎙 {x["by"]}\n\n'
    return msg


def _short(text, n=40):
    text = str(text or "").title()
    return text if len(text) <= n else text[: n - 1] + "…"


def _track_link(item):
    link = item.get("url")
    if link:
        return link
    vidid = str(item.get("vidid") or "")
    if "index_" in vidid or "live_" in vidid:
        return None
    if vidid and vidid not in ("telegram", "soundcloud"):
        return f"https://youtu.be/{vidid}"
    return None


def queue_list_html(_, got, buttons_html, what="g", shown: int = 15):
    """Yukki-style queue card: aside now-playing plus a bordered track table.

    Every up-next row carries a danger delete button; hidden rows are
    revealed with a single show-more callback button.
    """
    total = len(got)
    upnext = max(total - 1, 0)
    if shown < 1:
        shown = 15
    if shown > upnext:
        shown = upnext

    body = rich_heading(f'{pemoji("🗂")} ᴠᴇɴᴏᴍ ᴍᴜsɪᴄ ǫᴜᴇᴜᴇ ( {total} )', level=3)
    now = got[0]
    now_url = _track_link(now)
    now_title = _short(now.get("title"))
    now_head = f'<a href="{now_url}">{rich_esc(now_title)}</a>' if now_url else rich_esc(now_title)
    body += (
        f'<aside>{pemoji("🔴")} <b>ᴏɴ ɴᴏᴡ ᴘʟᴀʏɪɴɢ</b><br>{now_head}<br>'
        f'{pemoji("⏱")} {rich_esc(now.get("dur") or "--:--")}  •  '
        f'{pemoji("👤")} {rich_esc(now.get("by") or "ᴛʜᴇ ʜᴏꜱᴛ")}</aside>'
    )

    if upnext > 0:
        body += f'<p>{pemoji("🎼")} <b>ᴜᴘ ɴᴇxᴛ</b> ( {upnext} )</p>'
        body += '<table bordered striped compact>'
        body += (
            f'<tr><th>#</th><th>{pemoji("🎵")} ᴛʀᴀᴄᴋ</th><th>⏱</th>'
            f'<th>👤</th><th>🗑</th></tr>'
        )
        for i in range(1, shown + 1):
            x = got[i]
            row_url = _track_link(x)
            row_title = _short(x.get("title"))
            track_cell = (
                f'<a href="{row_url}">{rich_esc(row_title)}</a>'
                if row_url
                else rich_esc(row_title)
            )
            body += (
                f'<tr><td>{i}</td><td>{track_cell}</td>'
                f'<td>{rich_esc(x.get("dur") or "--:--")}</td>'
                f'<td>{rich_esc(x.get("by") or "ᴛʜᴇ ʜᴏꜱᴛ")}</td>'
                f'<td><tg-button type="callback_data" style="danger" '
                f'data="qdel {what}|{i}">✕</tg-button></td></tr>'
            )
        body += "</table>"
        if upnext > shown:
            body += rich_button_row(
                rich_button(
                    f'{pemoji("➕")} ꜱʜᴏᴡ ᴍᴏʀᴇ ( {upnext - shown} )',
                    f"qmore {what}",
                    style="primary",
                )
            )
    else:
        body += f'<footer>{pemoji("✨")} ᴛʜᴇ ᴜᴘ-ɴᴇxᴛ ǫᴜᴇᴜᴇ ɪꜱ ᴇᴍᴘᴛʏ</footer>'

    body += buttons_html
    return body


async def resolve_image(got, videoid, stream_type):
    file = got[0]["file"]
    if "live_" in file or "vid_" in file:
        return get_image(videoid)
    if "index_" in file:
        return config.STREAM_IMG_URL
    if videoid == "telegram":
        return (
            config.TELEGRAM_AUDIO_URL
            if stream_type == "Audio"
            else config.TELEGRAM_VIDEO_URL
        )
    if videoid == "soundcloud":
        return config.SOUNCLOUD_IMG_URL
    if "saavn" in videoid:
        details = await Platform.saavn.info(got[0]["url"])
        return details["thumb"]
    return get_image(videoid)


@app.on_message(command("QUEUE_COMMAND") & filters.group & ~BANNED_USERS)
@language
async def ping_com(client, message: Message, _):
    if message.command[0][0] == "c":
        chat_id = await get_cmode(message.chat.id)
        if chat_id is None:
            return await message.reply_text(_["setting_12"])
        try:
            await app.get_chat(chat_id)
        except Exception:
            return await message.reply_text(_["cplay_4"])
        cplay = "c"
    else:
        chat_id = message.chat.id
        cplay = "g"
    if not await is_active_chat(chat_id):
        return await message.reply_text(_["general_6"])
    got = db.get(chat_id)
    if not got:
        return await message.reply_text(_["queue_2"])
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = (got[0]["title"]).title()
    stream_type = (got[0]["streamtype"]).title()
    DUR = get_duration(got)
    image = await resolve_image(got, videoid, stream_type)
    run_info = None
    if DUR != "Unknown":
        run_info = (seconds_to_min(got[0]["played"]), got[0]["dur"])
    html = player_html(
        _, image, title, stream_type, user, run_info, cplay, videoid
    )
    basic[videoid] = True
    mid = await send_rich(chat_id, html)
    if not mid:
        return await message.reply_text(_["general_6"])
    if DUR != "Unknown":
        try:
            while db[chat_id][0]["vidid"] == videoid:
                await asyncio.sleep(7)
                if await is_active_chat(chat_id):
                    if basic[videoid]:
                        if await is_music_playing(chat_id):
                            html = player_html(
                                _,
                                image,
                                title,
                                stream_type,
                                user,
                                (
                                    seconds_to_min(db[chat_id][0]["played"]),
                                    db[chat_id][0]["dur"],
                                ),
                                cplay,
                                videoid,
                            )
                            await edit_rich(chat_id, mid, html)
                    else:
                        break
                else:
                    break
        except Exception:
            return


@app.on_callback_query(filters.regex("GetTimer") & ~BANNED_USERS)
async def quite_timer(client, CallbackQuery: CallbackQuery):
    try:
        await CallbackQuery.answer("ᴋᴇᴇᴘ ᴠɪʙɪɴ'")
    except Exception:
        pass


@app.on_callback_query(filters.regex("GetQueued") & ~BANNED_USERS)
@languageCB
async def queued_tracks(client, CallbackQuery: CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    what, videoid = callback_request.split("|")
    try:
        chat_id, channel = await get_channeplayCB(_, what, CallbackQuery)
    except Exception:
        return
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_6"], show_alert=True)
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    await CallbackQuery.answer()
    basic[videoid] = False
    buttons = queue_back_markup(_, what)
    body = queue_list_html(_, got, buttons, what=what)
    chat_id = CallbackQuery.message.chat.id
    mid = CallbackQuery.message.id
    from VenomX.utils.rich_panels import mark_panel_closed

    mark_panel_closed(chat_id, mid)
    if len(body) < 3500:
        await edit_rich(chat_id, mid, body)
        return
    link = await Ayushbin(plain_list_text(got))
    await edit_rich(
        chat_id,
        mid,
        rich_heading(f'{pemoji("🗂")} ᴠᴇɴᴏᴍ ᴍᴜsɪᴄ ǫᴜᴇᴜᴇ ( {len(got)} )', level=3)
        + f'<p>{rich_esc(_["queue_3"].format(link))}</p>'
        + buttons,
    )


@app.on_callback_query(filters.regex(r"^qdel ") & ~BANNED_USERS)
@ActualAdminCB
async def qdel_card(client, CallbackQuery, _):
    try:
        what, number = CallbackQuery.data.split(None, 1)[1].split("|")
        number = int(number)
    except Exception:
        try:
            await CallbackQuery.answer()
        except Exception:
            pass
        return
    try:
        room, channel = await get_channeplayCB(_, what, CallbackQuery)
    except Exception:
        return
    got = db.get(room)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    await CallbackQuery.answer()
    if number > 0 and number < len(got):
        got.pop(number)
    buttons = queue_back_markup(_, what)
    body = queue_list_html(_, got, buttons, what=what)
    chat_id = CallbackQuery.message.chat.id
    mid = CallbackQuery.message.id
    from VenomX.utils.rich_panels import mark_panel_closed

    mark_panel_closed(chat_id, mid)
    await edit_rich(chat_id, mid, body)


@app.on_callback_query(filters.regex(r"^qmore ") & ~BANNED_USERS)
@languageCB
async def qmore_card(client, CallbackQuery, _):
    what = CallbackQuery.data.split(None, 1)[1].strip()
    try:
        room, channel = await get_channeplayCB(_, what, CallbackQuery)
    except Exception:
        return
    got = db.get(room)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    await CallbackQuery.answer()
    buttons = queue_back_markup(_, what)
    body = queue_list_html(_, got, buttons, what=what, shown=len(got))
    chat_id = CallbackQuery.message.chat.id
    mid = CallbackQuery.message.id
    from VenomX.utils.rich_panels import mark_panel_closed

    mark_panel_closed(chat_id, mid)
    await edit_rich(chat_id, mid, body)


@app.on_callback_query(filters.regex("queue_back_timer") & ~BANNED_USERS)
@languageCB
async def queue_back(client, CallbackQuery: CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    cplay = callback_data.split(None, 1)[1]
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except Exception:
        return
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_6"], show_alert=True)
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    await CallbackQuery.answer(_["set_cb_8"], show_alert=True)
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = (got[0]["title"]).title()
    stream_type = (got[0]["streamtype"]).title()
    DUR = get_duration(got)
    image = await resolve_image(got, videoid, stream_type)
    run_info = None
    if DUR != "Unknown":
        run_info = (seconds_to_min(got[0]["played"]), got[0]["dur"])
    chat_id = CallbackQuery.message.chat.id
    mid = CallbackQuery.message.id
    if got[0].get("rich_mid") == mid:
        from VenomX.utils.rich_panels import reattach_from_db

        await reattach_from_db(_, chat_id, mid)
        return
    html = player_html(
        _, image, title, stream_type, user, run_info, cplay, videoid
    )
    basic[videoid] = True
    await edit_rich(chat_id, mid, html)
    if DUR != "Unknown":
        try:
            while db[chat_id][0]["vidid"] == videoid:
                await asyncio.sleep(7)
                if await is_active_chat(chat_id):
                    if basic[videoid]:
                        if await is_music_playing(chat_id):
                            html = player_html(
                                _,
                                image,
                                title,
                                stream_type,
                                user,
                                (
                                    seconds_to_min(db[chat_id][0]["played"]),
                                    db[chat_id][0]["dur"],
                                ),
                                cplay,
                                videoid,
                            )
                            await edit_rich(chat_id, mid, html)
                    else:
                        break
                else:
                    break
        except Exception:
            return
