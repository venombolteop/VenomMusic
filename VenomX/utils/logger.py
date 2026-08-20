
# All rights reserved.
from config import LOG, LOGGER_ID
from VenomX import app
from VenomX.utils.database import is_on_off


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
╔══════════════════════╗
  🎵 **{app.mention} Play Log**
╚══════════════════════╝

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
            try:
                if thumbnail:
                    await app.send_photo(
                        chat_id=LOGGER_ID,
                        photo=thumbnail,
                        caption=logger_text,
                    )
                else:
                    await app.send_message(
                        chat_id=LOGGER_ID,
                        text=logger_text,
                        disable_web_page_preview=True,
                    )
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
