# All rights reserved.
#
# Vote-skip: one 🗳 button on the now-playing card lets any member vote to
# skip. When enough members vote, the track changes through the same
# auto-advance path the queue uses — no admin rights required, and admins
# can out-vote a troll simply by pressing too.
#

from pyrogram import filters

import config
from strings import command  # noqa: F401  (keeps module style consistent)
from VenomX import app
from VenomX.core.call import Ayush
from VenomX.misc import db
from VenomX.utils.database import group_assistant
from VenomX.utils.rich_msg import send_note

# chat_id -> (track identity, set of voter ids)
VS_VOTES: dict = {}


def _track_key(head: dict) -> str:
    return f"{head.get('vidid')}|{str(head.get('title'))[:24]}"


@app.on_callback_query(filters.regex(r"VSkip\|(-?\d+)") & ~config.BANNED_USERS)
async def vskip_callback(client, CallbackQuery):
    try:
        chat_id = int(CallbackQuery.data.split("|")[1])
    except Exception:
        return await CallbackQuery.answer("Invalid vote context", show_alert=True)
    check = db.get(chat_id)
    if not check:
        VS_VOTES.pop(chat_id, None)
        return await CallbackQuery.answer("ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴋʜᴀʟɪ - ᴏᴛᴏ ꜱᴋɪᴘ ᴍᴜʀᴅᴀ", show_alert=True)

    head = check[0]
    key = _track_key(head)
    state = VS_VOTES.get(chat_id)
    if not state or state[0] != key:
        state = (key, set())
        VS_VOTES[chat_id] = state

    uid = CallbackQuery.from_user.id if CallbackQuery.from_user else 0
    voters = state[1]
    if uid in voters:
        return await CallbackQuery.answer("ᴜꜱᴇ ꜰᴛ ꜱᴋɪᴘ ᴘᴇʜʟᴇ ꜱᴇ ᴠᴏᴛᴇ ᴋᴇ ᴛᴜ!", show_alert=True)
    voters.add(uid)

    have = len(voters)
    need = max(2, int(config.VOTE_SKIP_LIMIT or 3))
    if have < need:
        return await CallbackQuery.answer(
            f" ᴠᴏᴛᴇ **{have}/{need}** (ᴄᴜʀʀᴇɴᴛ: {str(head.get('title'))[:36]})", show_alert=True
        )

    VS_VOTES.pop(chat_id, None)
    await CallbackQuery.answer()
    title = str(head.get("title"))[:36]
    await send_note(
        chat_id, f"🔥 ᴛᴏᴛᴇ-ꜱᴋɪᴘ**! ᴇᴍᴏᴄᴇꜱ **{have}** ᴏꜰ ᴜꜱ — ꜱᴏɴɢ **{title}** ꜱᴋɪᴘᴘᴇᴅ"
    )
    try:
        py_tgcalls_client = await group_assistant(Ayush, chat_id)
        await Ayush.change_stream(py_tgcalls_client, chat_id)
    except Exception as e:
        await send_note(chat_id, f"❌ ᴠᴏᴛᴇ-ꜱᴋɪᴘ ꜰᴀɪʟ: {type(e).__name__}")
