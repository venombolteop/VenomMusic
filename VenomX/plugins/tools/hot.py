# All rights reserved.
#
# /hot — per-chat leaderboard of the tracks this chat played the most.
# Plays are counted at card spawn (rich_panels._board_bump → mongo playstats).
#

from pyrogram import filters

from config import BANNED_USERS
from strings import command
from VenomX import app
from VenomX.utils.database import get_top_tracks
from VenomX.utils.decorators.language import language
from VenomX.utils.rich_msg import pemoji, reply_note, rich_esc, rich_heading, send_rich


@app.on_message(command("HOT_COMMAND") & filters.group & ~BANNED_USERS)
@language
async def hot_chart(client, message, _):
    tracks = await get_top_tracks(message.chat.id, 10)
    if not tracks:
        return await reply_note(
            message, f"{pemoji('🔥')} ꜱᴛɪʟʟ ᴄᴏʟᴅ — ᴘʟᴀʏ ꜱᴏᴍᴇ ᴛʀᴀᴄᴋꜱ ꜰɪʀꜱᴛ!"
        )
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for rank, t in enumerate(tracks, 1):
        badge = medals[rank - 1] if rank <= 3 else f"{rank}."
        title = rich_esc(str(t["title"])[:42])
        lines.append(f"{badge} <b>{title}</b> — <mark>{t['plays']} ᴘʟᴀʏꜱ</mark>")
    body = (
        rich_heading(f"{pemoji('🔥')} ᴠᴇɴᴏᴍ ʜᴏᴛ ᴄʜᴀʀᴛ", level=4)
        + "<hr/>"
        + "<aside>"
        + f"{pemoji('📊')} ᴛᴏᴘ ᴏꜰ ᴛʜɪꜱ ᴄʜᴀᴛ"
        + "</aside>"
        + "<blockquote>" + "<br>".join(lines) + "</blockquote>"
        + f"<footer>{pemoji('🎯')} ꜱᴛʀᴇᴀᴍ ꜱᴏɴɢꜱ ᴛᴏ ᴄʟɪᴍʙ ᴛʜᴇ ʙᴏᴀʀᴅ</footer>"
    )
    await send_rich(message.chat.id, body)
