
# All rights reserved.
#
# Bot added/left logger — rich-message cards (Bot API 10.3).
#

from pyrogram import filters
from pyrogram.types import Message

from config import LOG, LOGGER_ID
from VenomX import app
from VenomX.utils.database import delete_served_chat, get_assistant, is_on_off
from VenomX.utils.rich_msg import (
    pemoji,
    rich_esc,
    rich_url_button,
    rich_button_row,
    send_rich,
)


@app.on_message(filters.new_chat_members)
async def on_bot_added(_, message):
    try:
        if not await is_on_off(LOG):
            return

        userbot = await get_assistant(message.chat.id)
        chat = message.chat
        for members in message.new_chat_members:
            if members.id == app.id:
                count = await app.get_chat_members_count(chat.id)
                username = (
                    message.chat.username if message.chat.username else "ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ"
                )
                adder = message.from_user
                adder_name = rich_esc((adder.first_name if adder else "Unknown") or "Unknown")
                adder_id = adder.id if adder else 0
                body = (
                    f"<p>{pemoji('🧮')} <b>#New_Group</b></p>"
                    + f"<p>{pemoji('🚀')} ᴄʜᴀᴛ ɴᴀᴍᴇ: <b>{rich_esc(message.chat.title)}</b></p>"
                    + f"<p>{pemoji('🔗')} ᴄʜᴀᴛ ɪᴅ: <code>{message.chat.id}</code></p>"
                    + f"<p>{pemoji('👥')} ᴄʜᴀᴛ ᴜꜱᴇʀɴᴀᴍᴇ: @{rich_esc(username)}</p>"
                    + f"<p>{pemoji('🎧')} ᴍᴇᴍʙᴇʀꜱ: {count}</p>"
                    + f"<p>{pemoji('✨')} ᴀᴅᴅᴇᴅ ʙʏ: {adder_name}</p>"
                )
                await send_rich(
                    LOGGER_ID,
                    body
                    + rich_button_row(
                        rich_url_button(
                            f"{pemoji('✨')} ᴀᴅᴅᴇᴅ ʙʏ: {adder_name}",
                            f"tg://user?id={adder_id}",
                        )
                    ),
                )
                if message.chat.username:
                    await userbot.join_chat(message.chat.username)
    except Exception:
        pass


@app.on_message(filters.left_chat_member)
async def on_bot_kicked(_, message: Message):
    try:
        if not await is_on_off(LOG):
            return
        userbot = await get_assistant(message.chat.id)

        left_chat_member = message.left_chat_member
        if left_chat_member and left_chat_member.id == app.id:
            remover = message.from_user
            remove_by = rich_esc(
                remover.first_name if remover else "𝐔ɴᴋɴᴏᴡɴ 𝐔ꜱᴇʀ"
            )
            title = rich_esc(message.chat.title or "unknown")
            username = (
                f"@{rich_esc(message.chat.username)}" if message.chat.username else "ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ"
            )
            chat_id = message.chat.id
            remover_id = remover.id if remover else 0
            left = (
                f"<p>{pemoji('⚠')} <b>#Left_group</b></p>"
                f"<p>{pemoji('🚀')} ᴄʜᴀᴛ ɴᴀᴍᴇ: <b>{title}</b></p>"
                f"<p>{pemoji('🔗')} ᴄʜᴀᴛ ɪᴅ: <code>{chat_id}</code></p>"
                f"<p>{pemoji('👥')} ᴄʜᴀᴛ ᴜꜱᴇʀɴᴀᴍᴇ: {username}</p>"
                f"<p>{pemoji('✨')} ʀᴇᴍᴏᴠᴇᴅ ʙʏ: {remove_by}</p>"
            )
            await send_rich(
                LOGGER_ID,
                left
                + rich_button_row(
                    rich_url_button(
                        f"{pemoji('✨')} ʀᴇᴍᴏᴠᴇᴅ ʙʏ: {remove_by}",
                        f"tg://user?id={remover_id}",
                    )
                ),
            )
            await delete_served_chat(chat_id)
            await userbot.leave_chat(chat_id)
    except Exception as e:
        pass
