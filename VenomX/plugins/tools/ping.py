
# All rights reserved.
#
# Ping module — rich-message reply card (Bot API 10.3) + Venom branding.
#

from datetime import datetime

from config import BANNED_USERS, PING_IMG_URL
from strings import command
from VenomX import app
from VenomX.core.call import Ayush
from VenomX.utils import bot_sys_stats
from VenomX.utils.decorators.language import language
from VenomX.utils.inline import support_group_markup
from VenomX.utils.rich_msg import (
    edit_rich,
    pemoji,
    rich_esc,
    rich_heading,
    rich_img,
    send_rich,
)


@app.on_message(command("PING_COMMAND") & ~BANNED_USERS)
@language
async def ping_com(client, message, _):
    mid = await send_rich(
        message.chat.id,
        rich_img(PING_IMG_URL)
        + rich_heading(f'{pemoji("🏓")} ᴠᴇɴᴏᴍ ᴘɪɴɢ ᴄʜᴇᴄᴋ', level=4)
        + f"<p>{rich_esc(_['ping_1'].format(app.mention))}</p>"
        + support_group_markup(_),
    )
    start = datetime.now()
    pytgping = await Ayush.ping()
    UP, CPU, RAM, DISK = await bot_sys_stats()
    resp = (datetime.now() - start).microseconds / 1000
    body = (
        rich_img(PING_IMG_URL)
        + rich_heading(f'{pemoji("🏓")} ᴠᴇɴᴏᴍ ᴘɪɴɢ ʀᴇᴘʟʏ', level=4)
        + "<p>"
        + f"{pemoji('⚡')} <b>ᴘɪɴɢ</b>: {resp} ms\n\n"
        + f"{pemoji('🖥')} <b>ᴜᴘᴛɪᴍᴇ</b>: {UP}\n"
        + f"{pemoji('💾')} <b>ʀᴀᴍ</b>: {RAM}\n"
        + f"{pemoji('🧯')} <b>ᴄᴘᴜ</b>: {CPU}\n"
        + f"{pemoji('🌩')} <b>ᴅɪsᴋ</b>: {DISK}\n"
        + f"{pemoji('📞')} <b>ᴄʙ ʟᴀᴛᴇɴᴄʏ</b>: {pytgping}"
        + "</p>"
        + support_group_markup(_)
    )
    await edit_rich(message.chat.id, mid, body)
