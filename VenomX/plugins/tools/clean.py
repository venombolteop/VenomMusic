import os
import shutil

from pyrogram import filters

from VenomX import app
from VenomX.misc import SUDOERS
from VenomX.utils.rich_msg import reply_note, status_card


@app.on_message(filters.command("clean") & SUDOERS)
async def clean(_, message):
    A = await status_card(message.chat.id, "🧹 ᴄʟᴇᴀɴɪɴɢ ᴛᴇᴍᴘ ᴅɪʀᴇᴄᴛᴏʀɪᴇs...")
    dir = "downloads"
    dir1 = "cache"
    shutil.rmtree(dir)
    shutil.rmtree(dir1)
    os.mkdir(dir)
    os.mkdir(dir1)
    await A.edit("ᴛᴇᴍᴘ ᴅɪʀᴇᴄᴛᴏʀɪᴇs ᴀʀᴇ ᴄʟᴇᴀɴᴇᴅ")
