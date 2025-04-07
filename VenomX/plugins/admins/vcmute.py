
# All rights reserved.
#

from pyrogram import filters
from pyrogram.types import Message

from strings import command

from config import BANNED_USERS
from VenomX import app
from VenomX.core.call import Ayush
from VenomX.utils.database import is_muted, mute_off, mute_on
from VenomX.utils.decorators import AdminRightsCheck


@app.on_message(command("MUTE_COMMAND") & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def mute_admin(cli, message: Message, _, chat_id):
    if not len(message.command) == 1 or message.reply_to_message:
        return
    if await is_muted(chat_id):
        return await message.reply_text(_["admin_5"], disable_web_page_preview=True)
    await mute_on(chat_id)
    await Ayush.mute_stream(chat_id)
    await message.reply_text(
        _["admin_6"].format(message.from_user.mention), disable_web_page_preview=True
    )


@app.on_message(command("UNMUTE_COMMAND") & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def unmute_admin(Client, message: Message, _, chat_id):
    if not len(message.command) == 1 or message.reply_to_message:
        return
    if not await is_muted(chat_id):
        return await message.reply_text(_["admin_7"], disable_web_page_preview=True)
    await mute_off(chat_id)
    await Ayush.unmute_stream(chat_id)
    await message.reply_text(
        _["admin_8"].format(message.from_user.mention), disable_web_page_preview=True
    )
