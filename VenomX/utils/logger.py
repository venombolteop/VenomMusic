
# All rights reserved.
from config import LOG, LOGGER_ID
from VenomX import app
from VenomX.utils.database import is_on_off
from VenomX.utils.rich_msg import send_rich


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
        if chat_link:
            chat_line = f"🏷 **Chat:** [{chat_title}]({chat_link})"
        else:
            chat_line = f"🏷 **Chat:** {chat_title}"

        logger_text = f"""
╔══════════╗
  🎵 **{app.mention} Play Log**
╚══════════╝

🏰 **Group Info**
├ {chat_line}
├ 🆔 **Chat ID:** `{message.chat.id}`
└ 🔗 **Username:** {chatusername}

👤 **Requested By**
├ 🧑 **Name:** {user.mention}
├ 🆔 **User ID:** `{user.id}`
└ 🔗 **Username:** {username}

🎶 **Track Details**
├ 🔎 **Query:** `{query}`
└ 📡 **Stream:** `{streamtype}`

⚡ **Mode:** Direct Stream · Premium UI
"""
        if message.chat.id != LOGGER_ID:
            from VenomX.utils.rich_msg import rich_esc

            try:
                if thumbnail and str(thumbnail).startswith(("http://", "https://")):
                    html = (
                        f"<img src=\"{thumbnail}\"/>"
                        f"<p>{rich_esc(logger_text)}</p>"
                    )
                else:
                    html = f"<p>{rich_esc(logger_text)}</p>"
                html += (
                    "<tg-button-row>"
                    f'<tg-button type="url" style="primary" '
                    f'url="{chat_link or f"https://t.me/{chatusername.lstrip(chr(64))}"}">'
                    "🏷 Chat</tg-button></tg-button-row>"
                )
                await send_rich(LOGGER_ID, html)
            except Exception:
                try:
                    await app.send_message(
                        chat_id=LOGGER_ID,
                        text=logger_text,
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass
        return
