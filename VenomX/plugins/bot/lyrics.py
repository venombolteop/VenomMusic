# All rights reserved.
#

"""Per-chat switch for the synced lyrics panel.

The setting lives per chat rather than in one place on the server, so turning
it off in a busy group does not silence the panel everywhere else, and turning
it on where it was off does not affect the chats that had it. Chats that have
never been told either way use the configured default, which is on.
"""

from pyrogram import filters
from pyrogram.enums import ButtonStyle, ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup, Message

from strings import command
from VenomX import app, LOGGER
from VenomX.utils.database import get_vc_lyrics, set_vc_lyrics
from VenomX.utils.decorators.admins import AdminRightsCheck
from VenomX.utils.premium import close_btn, custom_btn
from VenomX.utils.stream import lyrics as lyrics_display

_LOG = "Lyrics"


def panel_markup(on: bool):
    """The on/off panel, with the current state spelled out on the buttons."""
    return InlineKeyboardMarkup(
        [
            [
                custom_btn(
                    "Lyrics: on" if on else "Lyrics: off",
                    callback_data="lyrics|off" if on else "lyrics|on",
                    style=ButtonStyle.SUCCESS if on else ButtonStyle.DANGER,
                    emoji="✅" if on else "❌",
                )
            ],
            [close_btn("Close")],
        ]
    )


async def _is_admin(message: Message) -> bool:
    """A callback carries no command decorator, so the admin check is explicit."""
    try:
        member = await message.chat.get_member(message.from_user.id)
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
    command("LYRICS_STATUS_COMMAND", prefixes=["/", "!", "%", ",", "@", "#"])
    & filters.group
)
async def lyrics_status(client, message: Message):
    chat_id = message.chat.id
    on = await get_vc_lyrics(chat_id)
    await message.reply_text(
        "🎵 <b>Lyrics in the voice chat panel</b>\n\n"
        "Lines follow the song as it plays, here in this chat only — "
        "switching it does not touch any other chat.\n\n"
        "Status: <b>{state}</b>".format(state="on" if on else "off"),
        reply_markup=panel_markup(on),
    )


@app.on_callback_query(filters.regex(r"^lyrics\|(on|off)$"))
async def lyrics_toggle(client, CallbackQuery):
    await CallbackQuery.answer()
    chat_id = CallbackQuery.message.chat.id
    if not await _is_admin(CallbackQuery.message):
        return await CallbackQuery.answer(
            "Only an admin can change this.", show_alert=True
        )

    want_on = CallbackQuery.matches[0].group(1) == "on"
    if await get_vc_lyrics(chat_id) == want_on:
        return await CallbackQuery.answer(
            "Lyrics is already {} here.".format("on" if want_on else "off"),
            show_alert=True,
        )

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

    return await CallbackQuery.edit_message_text(
        "🎵 <b>Lyrics in the voice chat panel</b>\n\n"
        "Lines follow the song as it plays, here in this chat only — "
        "switching it does not touch any other chat.\n\n"
        "Status: <b>{state}</b>".format(state="on" if want_on else "off"),
        reply_markup=panel_markup(want_on),
    )


@app.on_callback_query(filters.regex(r"^close$"))
async def lyrics_close(client, CallbackQuery):
    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass
    await CallbackQuery.answer()
