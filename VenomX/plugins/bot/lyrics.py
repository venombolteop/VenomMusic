# All rights reserved.
#

"""Per-chat switch for the synced lyrics panel.

The setting lives per chat rather than in one place on the server, so turning
it off in a busy group does not silence the panel everywhere else, and turning
it on where it was off does not affect the chats that had it. Chats that have
never been told either way use the configured default, which is on.
"""

import re
from datetime import datetime
from io import BytesIO

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message

from strings import command
from VenomX import Platform, app, LOGGER
from VenomX.utils.database import (
    get_lyrics_lang,
    get_vc_lyrics,
    set_lyrics_lang,
    set_vc_lyrics,
)
from VenomX.utils.decorators.admins import AdminRightsCheck
from VenomX.utils.rich_msg import (
    edit_rich,
    pemoji,
    rich_button,
    rich_button_row,
    rich_heading,
    send_rich,
)
from VenomX.utils.stream import lyrics as lyrics_display

_LOG = "Lyrics"


def panel_markup(on: bool):
    return (
        rich_button_row(
            rich_button(
                ("✅ ꜱᴛᴀᴛᴜꜱ: ᴏɴ" if on else "❌ ꜱᴛᴀᴛᴜꜱ: ᴏꜰꜰ"),
                callback_data="lyrics|off" if on else "lyrics|on",
                style="success" if on else "danger",
            )
        )
        + rich_button_row(
            rich_button("❌ ᴄʟᴏꜱᴇ", callback_data="close", style="danger")
        )
    )


async def _is_admin(chat, user_id: int) -> bool:
    """A callback carries no command decorator, so the admin check is explicit.

    The caller passes the clicker's id — CallbackQuery.message.from_user is the
    bot itself, which made the old check an admin-self-check in disguise.
    """
    try:
        member = await chat.get_member(user_id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


@app.on_message(
    command(["LYRICS_ON_COMMAND", "LYRICS_ENABLE_COMMAND"], prefixes=["/", "!", "%", ",", "@", "#"])
    & filters.group
)
@AdminRightsCheck
async def lyrics_on(client, message: Message):
    chat_id = message.chat.id
    if await get_vc_lyrics(chat_id):
        await message.reply_text(
            "🎵 Lyrics is <b>already on</b> in this chat.\n"
            "Use <code>/lyricsoff</code> to switch it off here."
        )
        return
    await set_vc_lyrics(chat_id, True)
    lyrics_display.forget(chat_id)
    LOGGER(_LOG).info("lyrics panel enabled for chat %s by %s", chat_id, message.from_user.id)
    await message.reply_text(
        "🎵 Lyrics <b>on</b> for this chat.\n"
        "Lines will appear in the voice chat panel as the song plays. "
        "This does not change any other chat."
    )


@app.on_message(
    command(["LYRICS_OFF_COMMAND", "LYRICS_DISABLE_COMMAND"], prefixes=["/", "!", "%", ",", "@", "#"])
    & filters.group
)
@AdminRightsCheck
async def lyrics_off(client, message: Message):
    chat_id = message.chat.id
    if not await get_vc_lyrics(chat_id):
        await message.reply_text(
            "🎵 Lyrics is <b>already off</b> in this chat.\n"
            "Use <code>/lyricson</code> to switch it on here."
        )
        return
    await set_vc_lyrics(chat_id, False)
    lyrics_display.stop(chat_id)
    lyrics_display.forget(chat_id)
    LOGGER(_LOG).info("lyrics panel disabled for chat %s by %s", chat_id, message.from_user.id)
    await message.reply_text(
        "🎵 Lyrics <b>off</b> for this chat.\n"
        "Nothing will be posted in the voice chat panel here. "
        "This does not change any other chat."
    )


@app.on_message(
    command(["LYRICS_STATUS_COMMAND", "LYRICS_TEXT_COMMAND"],
            prefixes=["/", "!", "%", ",", "@", "#"])
    & filters.group
)
async def lyrics_status(client, message: Message):
    """`/lyrics` on its own is the panel; `/lyrics <song>` looks one up."""
    asked = " ".join(message.command[1:]).strip()
    if asked:
        return await _lyrics_text(client, message, asked)
    chat_id = message.chat.id
    on = await get_vc_lyrics(chat_id)
    body = rich_heading(f'{pemoji("🎵")} ᴠᴇɴᴏᴍ ʟʏʀɪᴄꜱ ᴘᴀɴᴇʟ', level=4)
    body += f"<p>Lines ᴍᴏᴠᴇ ᴡɪᴛʜ ᴛʜᴇ ꜱᴏɴɢ ᴛɪᴍᴇ — ᴄʜᴀᴛ-ᴏɴʟʏ\nꜱᴛᴀᴛᴜꜱ: <b>{'ᴏɴ' if on else 'ᴏꜰꜰ'}</b></p>"
    body += panel_markup(on)
    await send_rich(chat_id, body)


@app.on_callback_query(filters.regex(r"^lyrics\|(on|off)$"))
async def lyrics_toggle(client, CallbackQuery):
    chat_id = CallbackQuery.message.chat.id
    if not await _is_admin(
        CallbackQuery.message.chat, CallbackQuery.from_user.id
    ):
        return await CallbackQuery.answer(
            "Only an admin can change this.", show_alert=True
        )

    want_on = CallbackQuery.matches[0].group(1) == "on"
    if await get_vc_lyrics(chat_id) == want_on:
        return await CallbackQuery.answer(
            "Lyrics is already {} here.".format("on" if want_on else "off"),
            show_alert=True,
        )
    try:
        await CallbackQuery.answer()
    except Exception:
        pass

    await set_vc_lyrics(chat_id, want_on)
    if want_on:
        lyrics_display.forget(chat_id)
    else:
        lyrics_display.stop(chat_id)
        lyrics_display.forget(chat_id)
    LOGGER(_LOG).info(
        "lyrics panel %s for chat %s by %s",
        "enabled" if want_on else "disabled",
        chat_id,
        CallbackQuery.from_user.id,
    )

    body = rich_heading(f'{pemoji("🎵")} ᴠᴇɴᴏᴍ ʟʏʀɪᴄꜱ ᴘᴀɴᴇʟ', level=4)
    body += f"<p>Lines ᴍᴏᴠᴇ ᴡɪᴛʜ ᴛʜᴇ ꜱᴏɴɢ ᴛɪᴍᴇ — ᴄʜᴀᴛ-ᴏɴʟʏ\nꜱᴛᴀᴛᴜꜱ: <b>{'ᴏɴ' if want_on else 'ᴏꜰꜰ'}</b></p>"
    body += panel_markup(want_on)
    return await edit_rich(CallbackQuery.message.chat.id, CallbackQuery.message.id, body)


LANG_STATES = {
    "auto": "whichever the song has",
    "hindi": "हिन्दी",
    "english": "English",
}


def lang_markup(current: str):
    return rich_button_row(
        *(
            rich_button(
                f"{label} ✓" if code == current else label,
                callback_data=f"lyricslang|{code}",
                style="success" if code == current else "primary",
            )
            for code, label in (
                ("auto", "ᴀᴜᴛᴏ"),
                ("hindi", "ʜɪɴᴅɪ"),
                ("english", "ᴇɴɢʟɪꜱʜ"),
            )
        )
    ) + rich_button_row(
        rich_button("❌ ᴄʟᴏꜱᴇ", callback_data="close", style="danger")
    )


@app.on_message(
    command("LYRICS_LANG_COMMAND", prefixes=["/", "!", "%", ",", "@", "#"])
    & filters.group
)
async def lyrics_lang(client, message: Message):
    current = await get_lyrics_lang(message.chat.id)
    body = rich_heading(f'{pemoji("🌐")} ʟʏʀɪᴄꜱ ʟᴀɴɢᴜᴀɢᴇ ꜱᴇᴛᴜᴘ', level=4)
    body += f"<p><b>ᴀᴜᴛᴏ</b> = ɢᴇᴛ ᴡʜᴀᴛᴇᴠᴇʀ ᴛʜᴇ ꜱᴏɴɢ ʜᴀꜱ\nᴄᴜʀʀᴇɴᴛ: <b>{LANG_STATES.get(current, current)}</b></p>"
    body += lang_markup(current)
    await send_rich(message.chat.id, body)


@app.on_callback_query(filters.regex(r"^lyricslang\|(auto|hindi|english)$"))
async def lyrics_lang_cb(client, CallbackQuery):
    if not await _is_admin(
        CallbackQuery.message.chat, CallbackQuery.from_user.id
    ):
        return await CallbackQuery.answer(
            "Only an admin can change this.", show_alert=True
        )
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    chat_id = CallbackQuery.message.chat.id
    want = CallbackQuery.matches[0].group(1)
    await set_lyrics_lang(chat_id, want)
    lyrics_display.forget(chat_id)
    LOGGER(_LOG).info("lyrics language for chat %s set to %s", chat_id, want)
    body = rich_heading(f'{pemoji("🌐")} ʟʏʀɪᴄꜱ ʟᴀɴɢᴜᴀɢᴇ ꜱᴇᴛᴜᴘ', level=4)
    body += f"<p><b>ᴀᴜᴛᴏ</b> = ɢᴇᴛ ᴡʜᴀᴛᴇᴠᴇʀ ᴛʜᴇ ꜱᴏɴɢ ʜᴀꜱ\nᴄᴜʀʀᴇɴᴛ: <b>{LANG_STATES.get(want, want)}</b></p>"
    body += lang_markup(want)
    return await edit_rich(CallbackQuery.message.chat.id, CallbackQuery.message.id, body)


async def _lyrics_text(client, message: Message, query: str):
    """The timed lines as a message anyone can read.

    Independent of the voice chat: a lyric can be looked up without anything
    playing, which is the whole point of asking for one by name.
    """
    if not query.strip():
        await message.reply_text(
            "🎵 <b>Usage</b>\n<code>/lyrics kesariya</code>"
        )
        return

    status = await message.reply_text("🎵 <b>Searching lyrics…</b>")
    try:
        details, vidid = await Platform.youtube.track(query)
    except Exception:
        return await status.edit_text("❌ Could not find that song.")

    seconds = None
    try:
        from VenomX.utils.formatters import time_to_seconds

        seconds = time_to_seconds(details.get("duration_min") or "")
    except Exception:
        seconds = None

    # The performer comes from the same lookup the title came from, so it is
    # free. Passing it lets the API disambiguate instead of guessing.
    _artist = details.get("uploader") or details.get("channel") or None
    lines = await lyrics_display.fetch(
        details.get("title") or query, seconds, chat_id=message.chat.id,
        artist=_artist,
    )
    if not lines:
        return await status.edit_text(
            "❌ No timed lyrics for <b>{title}</b>.".format(
                title=(details.get("title") or query)[:40]
            )
        )

    title = (details.get("title") or query)[:60]

    # As a file, with every line. A long song does not fit in a message, and
    # cutting it at forty lines meant the chorus was often the part that went
    # missing. The file also keeps the timestamps, so it opens in any player
    # that follows along.
    safe = re.sub(r'[\\/:*?"<>|]+', "_", title).strip() or "lyrics"
    lrc = "\n".join(
        "[{m:02d}:{s:02d}.{h:02d}]{text}".format(
            m=int(t // 60),
            s=int(t % 60),
            h=int((t % 1) * 100),
            text=text,
        )
        for t, text in lines
    )
    body_lrc = (
        f"[ti:{title}]\n"
        f"[length:{details.get('duration_min') or ''}]\n\n"
        f"{lrc}\n"
    )

    buffer = BytesIO()
    buffer.write(body_lrc.encode("utf-8"))
    buffer.seek(0)

    await status.delete()
    await message.reply_document(
        document=buffer,
        file_name=f"{safe}.lrc",
        caption=(
            "🎵 <b>{title}</b>\n"
            "<i>{count} timed lines</i>\n\n"
            "<i>Play it with</i> <code>/play {title}</code>"
        ).format(title=title, count=len(lines)),
    )


@app.on_callback_query(filters.regex(r"^close$"))
async def lyrics_close(client, CallbackQuery):
    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass
    await CallbackQuery.answer()
