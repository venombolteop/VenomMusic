
# All rights reserved.
from config import LOG, LOGGER_ID
from VenomX import app
from VenomX.utils.database import is_on_off
from VenomX.utils.rich_msg import (
    pemoji,
    rich_button_row,
    rich_esc,
    rich_heading,
    rich_kv,
    rich_note,
    rich_url_button,
    send_rich,
)


async def play_logs(message, streamtype, thumbnail=None):
    if await is_on_off(LOG):
        if message.chat.username:
            chatusername = f"@{message.chat.username}"
            chat_link = f"https://t.me/{message.chat.username}"
        else:
            chatusername = "Private Group"
            chat_link = None

        user = message.from_user
        username = f"@{user.username}" if user.username else "No Username"
        try:
            query = message.text.split(None, 1)[1]
        except Exception:
            query = message.text or "N/A"

        chat_title = message.chat.title or "Unknown"

        # Rich-native log card: heading, optional thumb, callout info block
        # with highlighted values, footer and a centered chat link button.
        # No tree art and no markdown — rich HTML renders none of that.
        html = rich_heading("🎵 ᴠᴇɴᴏᴍ ᴘʟᴀʏ ʟᴏɢ", level=4)
        thumb = str(thumbnail) if thumbnail else ""
        if thumb.startswith(("http://", "https://")):
            html += f'<img src="{thumb}"/>'
        info = (
            f"{pemoji('🏰')} {rich_kv('Chat:', chat_title)}<br>"
            f"{pemoji('🆔')} {rich_kv('ID:', message.chat.id)}<br>"
            f"{pemoji('🔗')} {rich_kv('Username:', chatusername)}<br>"
            f"{pemoji('👤')} {rich_esc(user.mention)}<br>"
            f"{pemoji('🆔')} {rich_kv('ID:', user.id)}<br>"
            f"{pemoji('🔗')} {rich_kv('Username:', username)}<br>"
            f"{pemoji('🔎')} {rich_kv('Query:', str(query)[:120])}<br>"
            f"{pemoji('📡')} {rich_kv('Stream:', str(streamtype))}"
        )
        html += rich_note(info)
        html += f"<footer>{app.mention} · ᴅɪʀᴇᴄᴛ ꜱᴛʀᴇᴀᴍ</footer>"
        target = chat_link or f"https://t.me/{str(chatusername).lstrip('@')}"
        html += rich_button_row(
            rich_url_button("🏷 ᴏᴘᴇɴ ᴄʜᴀᴛ", target, style="primary"),
            align="center",
        )

        if message.chat.id != LOGGER_ID:
            await send_rich(LOGGER_ID, html)
