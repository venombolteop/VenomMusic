
# All rights reserved.
#
# Logger play-log — classic tree card, sent as photo (thumbnail) + caption.

from pyrogram.enums import ParseMode

from config import LOG, LOGGER_ID
from VenomX import app
from VenomX.utils.database import is_on_off
from VenomX.utils.rich_msg import rich_esc


def _or_dash(value):
    value = str(value or "").strip()
    return value if value else "—"


async def play_logs(message, streamtype, thumbnail=None):
    if not await is_on_off(LOG):
        return
    if message.chat.id == LOGGER_ID:
        return

    user = message.from_user
    try:
        query = message.text.split(None, 1)[1]
    except Exception:
        query = message.text or "N/A"
    query = _or_dash(query)[:120]

    if message.chat.username:
        username = f"@{message.chat.username}"
        chat_link = f"https://t.me/{message.chat.username}"
        chat_name = (
            f'<a href="{chat_link}">'
            f"{rich_esc(message.chat.title or 'Unknown')}</a>"
        )
    else:
        username = "—"
        chat_name = rich_esc(message.chat.title or "Private Group")

    bot_name = rich_esc(getattr(app, "name", None) or "VenomMusic")

    text = (
        "╔══════════╗\n"
        f"  🎵 {bot_name} ᴘʟᴀʏ ʟᴏɢ\n"
        "╚══════════╝\n\n"
        "🏰 ᴄʜᴀᴛ ɪɴꜰᴏ\n"
        f"├ 🏷 ᴄʜᴀᴛ : {chat_name}\n"
        f"├ 🆔 ᴄʜᴀᴛ ɪᴅ : <code>{_or_dash(message.chat.id)}</code>\n"
        f"└ 🔗 ᴜsᴇʀɴᴀᴍᴇ : {rich_esc(username)}\n\n"
        "👤 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ\n"
        f"├ 🧑 ɴᴀᴍᴇ : {user.mention}\n"
        f"├ 🆔 ᴜꜱᴇʀ ɪᴅ : <code>{_or_dash(user.id)}</code>\n"
        f"└ 🔗 ᴜsᴇʀɴᴀᴍᴇ : {rich_esc('@' + user.username) if user.username else '—'}\n\n"
        "🎶 ᴛʀᴀᴄᴋ ᴅᴇᴛᴀɪʟs\n"
        f"├ 🔎 ᴏᴜᴇʀʏ : {rich_esc(query)}\n"
        f"└ 📡 ꜱᴛʀᴇᴀᴍ : {rich_esc(str(streamtype))}\n\n"
        "⚡ ᴍᴏᴅᴇ : ᴅɪʀᴇᴄᴛ ꜱᴛʀᴇᴀᴍ · ᴘʀᴇᴍɪᴜᴍ ᴜɪ"
    )

    if thumbnail and str(thumbnail).startswith(("http://", "https://")):
        try:
            await app.send_photo(
                LOGGER_ID,
                photo=str(thumbnail),
                caption=text,
                parse_mode=ParseMode.HTML,
            )
            return
        except Exception:
            pass
    try:
        await app.send_message(LOGGER_ID, text, parse_mode=ParseMode.HTML)
    except Exception:
        pass
