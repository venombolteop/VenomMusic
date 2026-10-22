# All rights reserved.
#
from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from strings import command
from VenomX import app
from VenomX.utils.database import get_instant_play
from VenomX.utils.decorators import language
from VenomX.utils.inline.settings import instantplay_markup
from VenomX.utils.rich_msg import rich_esc, send_rich


@app.on_message(command("INSTANT_PLAY_COMMAND") & filters.group & ~BANNED_USERS)
@language
async def instantplay_mar(client, message: Message, _):
    instant = await get_instant_play(message.chat.id)
    buttons = instantplay_markup(_, instant)
    status = "✅ Enabled" if instant else "❌ Disabled"
    await send_rich(
        message.chat.id,
        f"<p>{rich_esc(_['instantplay_1'].format(message.chat.title, status))}</p>{buttons}",
    )
