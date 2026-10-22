
# All rights reserved.
#
# Helper module — rich-message help panels (Bot API 10.3) + Venom branding.
#

import logging
import re
from math import ceil
from typing import Union

from pyrogram import filters, types
from pyrogram.types import Message

from config import BANNED_USERS, START_IMG_URL
from strings import get_string, command, helpers, get_command
from VenomX import HELPABLE, app
from VenomX.utils.database import get_lang, is_commanddelete_on
from VenomX.utils.decorators.language import LanguageStart
from VenomX.utils.inline.start import private_help_panel
from VenomX.utils.rich_msg import (
    edit_rich,
    pemoji,
    rich_button,
    rich_button_row,
    rich_esc,
    rich_heading,
    rich_img,
    rich_md,
    send_rich,
)

COLUMN_SIZE = 4  # buttons per page column
NUM_COLUMNS = 3  # buttons per row


async def format_helper_text(lng, helper_key: str, text: str) -> str:
    if not text:
        return ""
    _ = get_command(lng)

    def _cmd(key):
        return " ".join(f"/{cmd}" for cmd in _[key])

    if helper_key == "Auth":
        return text.format(
            _cmd("AUTH_COMMAND"), _cmd("UNAUTH_COMMAND"), _cmd("AUTHUSERS_COMMAND")
        )
    elif helper_key == "Admin":
        return text.format(
            _cmd("PAUSE_COMMAND"),
            _cmd("RESUME_COMMAND"),
            _cmd("MUTE_COMMAND"),
            _cmd("UNMUTE_COMMAND"),
            _cmd("SKIP_COMMAND"),
            _cmd("STOP_COMMAND"),
            _cmd("SHUFFLE_COMMAND"),
            _cmd("SEEK_COMMAND"),
            _cmd("SEEK_BACK_COMMAND"),
            _cmd("REBOOT_COMMAND"),
            _cmd("LOOP_COMMAND"),
        )
    elif helper_key == "Active":
        return text.format(
            _cmd("ACTIVEVC_COMMAND"),
            _cmd("ACTIVEVIDEO_COMMAND"),
            _cmd("AC_COMMAND"),
            _cmd("STATS_COMMAND"),
        )
    elif helper_key == "Play":
        return text.format(
            _cmd("PLAY_COMMAND"),
            _cmd("PLAYMODE_COMMAND"),
            _cmd("CHANNELPLAY_COMMAND"),
            _cmd("STREAM_COMMAND"),
        )
    elif helper_key == "G-cast":
        return text.format(_cmd("BROADCAST_COMMAND"))
    elif helper_key == "Bot":
        return text.format(
            _cmd("GSTATS_COMMAND"),
            _cmd("SUDOUSERS_COMMAND"),
            _cmd("LYRICS_COMMAND"),
            _cmd("SONG_COMMAND"),
            _cmd("QUEUE_COMMAND"),
            _cmd("AUTHORIZE_COMMAND"),
            _cmd("UNAUTHORIZE_COMMAND"),
            _cmd("AUTHORIZED_COMMAND"),
        )
    elif helper_key == "P-List":
        return text.format(
            _cmd("PLAYLIST_COMMAND"),
            _cmd("DELETE_PLAYLIST_COMMAND"),
            _cmd("PLAY_PLAYLIST_COMMAND"),
            _cmd("PLAY_PLAYLIST_COMMAND"),
        )
    elif helper_key == "B-list":
        return text.format(
            _cmd("BLACKLISTCHAT_COMMAND"),
            _cmd("WHITELISTCHAT_COMMAND"),
            _cmd("BLACKLISTEDCHAT_COMMAND"),
            _cmd("BLOCK_COMMAND"),
            _cmd("UNBLOCK_COMMAND"),
            _cmd("BLOCKED_COMMAND"),
            _cmd("GBAN_COMMAND"),
            _cmd("UNGBAN_COMMAND"),
            _cmd("GBANNED_COMMAND"),
        )
    elif helper_key == "Dev":
        return text.format(
            _cmd("ADDSUDO_COMMAND"),
            _cmd("DELSUDO_COMMAND"),
            _cmd("SUDOUSERS_COMMAND"),
            _cmd("USAGE_COMMAND"),
            _cmd("GETVAR_COMMAND"),
            _cmd("DELVAR_COMMAND"),
            _cmd("SETVAR_COMMAND"),
            _cmd("RESTART_COMMAND"),
            _cmd("UPDATE_COMMAND"),
            _cmd("SPEEDTEST_COMMAND"),
            _cmd("MAINTENANCE_COMMAND"),
            _cmd("LOGGER_COMMAND"),
            _cmd("GETLOG_COMMAND"),
            _cmd("AUTOEND_COMMAND"),
        )
    else:
        return text


async def paginate_modules(page_n, chat_id: int, close: bool = False):
    """Rich-message version — returns an HTML fragment with button rows."""
    language = await get_lang(chat_id)
    helpers_dict = helpers.get(language, helpers.get("en", {}))

    _HELP_EMOJIS = [
        "🌟", "🔥", "🚀", "⭐", "💫", "✨", "🎵", "🎶", "🎧", "🎤",
        "💜", "🧡", "💛", "💚", "💙", "💖", "⚡", "🎯", "🎲", "🎮",
        "📌", "🔁", "🖥", "👑", "🌈", "🌙", "☀", "🌸", "🍀", "🦋",
    ]

    cell = [
        rich_button(
            f"{pemoji(emoji)} {rich_esc(text)}",
            callback_data=cb,
            style="primary",
        )
        for text, cb, emoji in _cells(helpers_dict, HELPABLE, close, page_n, _HELP_EMOJIS)
    ]

    rows = [
        rich_button_row(*cell[i : i + NUM_COLUMNS])
        for i in range(0, len(cell), NUM_COLUMNS)
    ]

    max_num_pages = ceil(len(rows) / COLUMN_SIZE) if rows else 1
    modulo_page = page_n % max_num_pages

    nav = rich_button_row(
        rich_button(f"{pemoji('⬅')} ᴘʀᴇᴠ", callback_data=f"help_prev({modulo_page - 1 if modulo_page > 0 else max_num_pages - 1},{int(close)})", style="primary"),
        rich_button("✅ ᴄʟᴏsᴇ" if close else f"{pemoji('🚀')} ʙᴀᴄᴋ", callback_data="close" if close else "settingsback_helper", style="danger" if close else "primary"),
        rich_button(f"{pemoji('➡')} ɴᴇxᴛ", callback_data=f"help_next({modulo_page + 1},{int(close)})", style="primary"),
    )

    page_rows = rows[modulo_page * COLUMN_SIZE : COLUMN_SIZE * (modulo_page + 1)] + [
        nav
    ]

    body = rich_heading(f'{pemoji("📚")} ᴠᴇɴᴏᴍ ᴄᴏᴍᴍᴀɴᴅ ᴢᴏɴᴇ', level=4)
    body += "".join(page_rows)
    return body


def _cells(helpers_dict, HELPABLE, close, page_n, emojis):
    out = []
    offset = len(helpers_dict)
    for i, helper_key in enumerate(helpers_dict):
        out.append(
            (
                helper_key,
                f"help_helper({helper_key.replace(',', '%44')},{page_n},{int(close)})",
                emojis[i % len(emojis)],
            )
        )
    for i, x in enumerate(HELPABLE.values()):
        out.append(
            (
                x.__MODULE__,
                "help_module({},{},{})".format(
                    x.__MODULE__.lower(), page_n, int(close)
                ),
                emojis[(offset + i) % len(emojis)],
            )
        )
    return out


@app.on_message(command("HELP_COMMAND") & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex("settings_back_helper") & ~BANNED_USERS)
async def helper_private(
    client: app, update: Union[types.Message, types.CallbackQuery]
):
    is_callback = isinstance(update, types.CallbackQuery)
    body = await paginate_modules(0, update.chat.id if not is_callback else update.message.chat.id, close=not is_callback)
    if is_callback:
        try:
            await update.answer()
        except Exception:
            pass
        chat_id = update.message.chat.id
        language = await get_lang(chat_id)
        _ = get_string(language)
        await edit_rich(
            chat_id,
            update.message.id,
            rich_img(START_IMG_URL) + body if START_IMG_URL else body,
        )
    else:
        chat_id = update.chat.id
        if await is_commanddelete_on(update.chat.id):
            try:
                await update.delete()
            except Exception:
                pass
        language = await get_lang(chat_id)
        _ = get_string(language)
        body_top = rich_img(START_IMG_URL) if START_IMG_URL else ""
        body_top += f"<p>{rich_esc(_['help_1'])}</p>"
        await send_rich(chat_id, body_top + body)


@app.on_message(command("HELP_COMMAND") & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client, message: Message, _):
    await send_rich(
        message.chat.id,
        rich_heading(f'{pemoji("📚")} ᴠᴇɴᴏᴍ HELP', level=4)
        + f"<p>{rich_esc(_['help_2'])}</p>"
        + private_help_panel(_),
    )


@app.on_callback_query(filters.regex(r"help_(.*?)"))
async def help_button(client, query):
    mod_match = re.match(r"help_module\((.+?),(.+?),(\d+)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?),(\d+)\)", query.data)
    next_match = re.match(r"help_next\((.+?),(\d+)\)", query.data)
    helper_match = re.match(r"help_helper\((.+?),(.+?),(\d+)\)", query.data)

    try:
        language = await get_lang(query.message.chat.id)
        _ = get_string(language)
        helpers_dict = helpers.get(language, helpers.get("en"))

    except Exception:
        language = "en"
        _ = get_string("en")
        helpers_dict = helpers.get("en", {})

    chat_id = query.message.chat.id
    mid = query.message.id
    top_text = _["help_1"]

    if mod_match:
        module = mod_match.group(1)
        prev_page_num = int(mod_match.group(2))
        close = bool(int(mod_match.group(3)))
        text = (
            f"<b><u>ʜᴇʟᴘ ɢᴜɪᴅᴇ ꜰᴏʀ {rich_esc(HELPABLE[module].__MODULE__)}:</u></b>"
            + rich_md(HELPABLE[module].__HELP__)
        )
        key = rich_button_row(
            rich_button(f"{pemoji('🚀')} ʙᴀᴄᴋ", callback_data=f"help_prev({prev_page_num},{int(close)})", style="primary"),
            rich_button(f"{pemoji('❌')} ᴄʟᴏsᴇ", callback_data="close", style="danger"),
        )
        body = rich_heading(f'{pemoji("📖")} ᴍᴏᴅᴜʟᴇ ɢᴜɪᴅᴇ', level=4)
        body += f"<p>{text}</p>"
        body += key
        await edit_rich(chat_id, mid, body)
    elif prev_match:
        curr_page = int(prev_match.group(1))
        close = bool(int(prev_match.group(2)))
        body = f"<p><b>{rich_esc(top_text)}</b></p>" + await paginate_modules(
            curr_page, chat_id, close=close
        )
        await edit_rich(chat_id, mid, body)
    elif next_match:
        next_page = int(next_match.group(1))
        close = bool(int(next_match.group(2)))
        body = f"<p><b>{rich_esc(top_text)}</b></p>" + await paginate_modules(
            next_page, chat_id, close=close
        )
        await edit_rich(chat_id, mid, body)
    elif helper_match:
        helper_key = helper_match.group(1).replace("%44", ",")
        page_n = int(helper_match.group(2))
        close = bool(int(helper_match.group(3)))
        raw_text = helpers_dict.get(helper_key, None)
        formatted_text = await format_helper_text(language, helper_key, raw_text)
        key = rich_button_row(
            rich_button(f"{pemoji('🚀')} ʙᴀᴄᴋ", callback_data=f"help_prev({page_n},{int(close)})", style="primary"),
            rich_button(f"{pemoji('❌')} ᴄʟᴏsᴇ", callback_data="close", style="danger"),
        )
        body = rich_heading(f'{pemoji("🎧")} {rich_esc(helper_key)}', level=4)
        body += f"<p>{rich_md(formatted_text)}</p>"
        body += key
        try:
            await edit_rich(chat_id, mid, body)
        except Exception as e:
            logging.exception(e)

    try:
        await client.answer_callback_query(query.id)
    except Exception:
        pass
