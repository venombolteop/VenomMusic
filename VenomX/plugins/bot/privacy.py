from pyrogram import filters
from pyrogram.types import Message

import config
from VenomX import app
from VenomX.utils.rich_msg import (
    pemoji,
    rich_esc,
    rich_heading,
    rich_url_button,
    rich_button_row,
    send_rich,
)

def privacy_html():
    return (
        rich_heading(f'{pemoji("🔒")} ᴘʀɪᴠᴀᴄʏ ᴢᴏɴᴇ', level=4)
        + f"<p>{pemoji('🔒')} <b>{rich_esc(app.mention)}</b> ᴘʀɪᴠᴀᴄʏ ꜱᴇᴛᴜᴘ</p>"
        + f"<p>{pemoji('🔗')} <a href='{config.PRIVACY_LINK}'>ᴘʀɪᴠᴀᴄʏ ᴇxᴇᴄᴜᴛᴏʀ</a></p>"
        + f"<p>{pemoji('💬')} <a href='{config.SUPPORT_GROUP}'>ꜱᴜᴘᴘᴏʀᴛ ᴛᴇᴀᴍ</a></p>"
    )


@app.on_message(filters.command("privacy"))
async def privacy(client, message: Message):
    await send_rich(
        message.chat.id,
        privacy_html()
        + rich_button_row(
            rich_url_button("🔒 ᴠɪᴇᴡ ᴘᴏʟɪᴄʏ", config.PRIVACY_LINK),
        ),
    )
