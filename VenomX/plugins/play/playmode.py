
# All rights reserved.
#

from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from strings import command
from VenomX import app
from VenomX.utils.database import get_playmode, get_playtype, is_nonadmin_chat
from VenomX.utils.decorators import language
from VenomX.utils.inline.settings import playmode_users_markup
from VenomX.utils.rich_msg import rich_esc, send_rich


@app.on_message(command("PLAYMODE_COMMAND") & filters.group & ~BANNED_USERS)
@language
async def playmode_(client, message: Message, _):
    playmode = await get_playmode(message.chat.id)
    if playmode == "Direct":
        Direct = True
    else:
        Direct = None
    is_non_admin = await is_nonadmin_chat(message.chat.id)
    if not is_non_admin:
        Group = True
    else:
        Group = None
    playty = await get_playtype(message.chat.id)
    if playty == "Everyone":
        Playtype = None
    else:
        Playtype = True
    buttons = playmode_users_markup(_, Direct, Group, Playtype)
    await send_rich(
        message.chat.id,
        f"<p>{rich_esc(_['playmode_1'].format(message.chat.title))}</p>{buttons}",
    )
