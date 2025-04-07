
# All rights reserved.
#

from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from strings import command
from VenomX import app
from VenomX.core.call import Ayush
from VenomX.utils.database import is_music_playing, music_on
from VenomX.utils.decorators import AdminRightsCheck


@app.on_message(command("RESUME_COMMAND") & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def resume_com(cli, message: Message, _, chat_id):
    if not len(message.command) == 1:
        return await message.reply_text(_["general_2"])
    if await is_music_playing(chat_id):
        return await message.reply_text(_["admin_3"])
    await music_on(chat_id)
    await Ayush.resume_stream(chat_id)
    await message.reply_text(_["admin_4"].format(message.from_user.mention))
