# All rights reserved.
#
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

from config import BANNED_USERS
from strings import command
from VenomX import app
from VenomX.utils.database import get_instant_play
from VenomX.utils.decorators import language
from VenomX.utils.inline.settings import instantplay_markup


@app.on_message(command("INSTANT_PLAY_COMMAND") & filters.group & ~BANNED_USERS)
@language
async def instantplay_mar(client, message: Message, _):
    instant = await get_instant_play(message.chat.id)
    buttons = instantplay_markup(_, instant)
    await message.reply_text(
        _["instantplay_1"].format(message.chat.title, "✅ Enabled" if instant else "❌ Disabled"),
        reply_markup=InlineKeyboardMarkup(buttons),
    )