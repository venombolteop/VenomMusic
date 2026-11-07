# All rights reserved.
#
# Vote-skip: one 🗳 button on the now-playing card lets any group member vote
# to skip. Accumulated per current track: enough votes advance the queue the
# same way stream_end auto-advance does. Admins skip instantly via the button
# or /skip; everyone else casts a vote — and typing /skip as a non-admin also
# counts as a vote (with progress shown in chat) instead of an access error.
#

from pyrogram import filters
from pyrogram.enums import ChatType

import config
from strings import command as _command
from VenomX import app
from VenomX.core.call import Ayush
from VenomX.misc import SUDOERS, db
from VenomX.utils.database import group_assistant
from VenomX.utils.rich_msg import pemoji, reply_note, send_note

# chat_id -> (track identity key, set of voter ids)
VS_VOTES: dict = {}


def _track_key(head: dict) -> str:
    return f"{head.get('vidid')}|{str(head.get('title'))[:24]}"


async def _is_vc_admin(client, chat_id: int, uid: int) -> bool:
    if uid in SUDOERS:
        return True
    try:
        m = await app.get_chat_member(chat_id, uid)
        return bool(m and m.privileges and m.privileges.can_manage_video_chats)
    except Exception:
        return False


async def _cast_vote(chat_id: int, uid: int, title: str) -> tuple:
    """Adds the vote. Returns (have, need, was_duplicate)."""
    check = db.get(chat_id)
    if not check:
        VS_VOTES.pop(chat_id, None)
        return (0, 0, False)

    head = check[0]
    key = _track_key(head)
    state = VS_VOTES.get(chat_id)
    if not state or state[0] != key:
        state = (key, set())
        VS_VOTES[chat_id] = state

    voters = state[1]
    if uid in voters:
        return (0, 0, True)
    voters.add(uid)

    need = max(2, int(config.VOTE_SKIP_LIMIT or 3))
    return (len(voters), need, False)


async def _run_vote_skip(chat_id: int, title: str, voters: int = 1):
    await send_note(
        chat_id,
        f"{pemoji('🚫')} ꜱᴋɪᴘᴘᴇᴅ — <b>{title}</b>"
        + (f" <i>({voters} ᴠᴏᴛᴇꜱ)</i>" if voters > 1 else ""),
    )
    try:
        py_tgcalls_client = await group_assistant(Ayush, chat_id)
        await Ayush.change_stream(py_tgcalls_client, chat_id)
    except Exception as e:
        await send_note(chat_id, f"❌ ꜱᴋɪᴘ ꜰᴀɪʟ: {type(e).__name__}")


@app.on_callback_query(filters.regex(r"VSkip\|(-?\d+)") & ~config.BANNED_USERS)
async def vskip_callback(client, CallbackQuery):
    try:
        chat_id = int(CallbackQuery.data.split("|")[1])
    except Exception:
        return await CallbackQuery.answer("ᴠᴏᴛᴇ ᴄᴏɴᴛᴇxᴛ ɪɴᴠᴀʟɪᴅ!", show_alert=True)

    chat_type = CallbackQuery.message.chat.type
    if chat_type == ChatType.PRIVATE:
        return await CallbackQuery.answer("ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ꜰᴏʀ ɢʀᴏᴜᴘ ᴠᴄꜱ!", show_alert=True)

    check = db.get(chat_id)
    if not check:
        VS_VOTES.pop(chat_id, None)
        return await CallbackQuery.answer("ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴇᴍᴘᴛʏ — ᴋᴜᴄʜ ᴘʟᴀʏ ᴋᴀʀᴏ!", show_alert=True)

    head = check[0]
    title = str(head.get("title"))[:36]

    uid = CallbackQuery.from_user.id if CallbackQuery.from_user else 0
    if await _is_vc_admin(client, chat_id, uid):
        # Admins don't need a poll.
        VS_VOTES.pop(chat_id, None)
        await CallbackQuery.answer("ᴀᴅᴍɪɴ ꜱᴋɪᴘ!", show_alert=True)
        return await _run_vote_skip(chat_id, title)

    have, need, dup = await _cast_vote(chat_id, uid, title)
    if dup:
        return await CallbackQuery.answer("ᴘᴇʜʟᴇ ꜱᴇ ᴠᴏᴛᴇ ᴋ ᴄʜᴜᴋᴇ!", show_alert=True)
    if have == 0:
        return await CallbackQuery.answer("ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴇᴍᴘᴛʏ — ᴋᴜᴄʜ ᴘʟᴀʏ ᴋᴀʀᴏ!", show_alert=True)

    if have < need:
        return await CallbackQuery.answer(f"ᴠᴏᴛᴇ ᴄᴏᴜɴᴛᴇᴅ • {have}/{need} ᴊᴜꜱᴛ {title}", show_alert=True)

    VS_VOTES.pop(chat_id, None)
    await CallbackQuery.answer("ꜱᴋɪᴘ ᴏᴛᴇ ᴘᴀꜱꜱ — ꜱᴋɪꜱᴇ ᴊᴜꜱᴛ!", show_alert=True)
    await _run_vote_skip(chat_id, title, have)


@app.on_message(_command("SKIP_COMMAND") & filters.group & ~config.BANNED_USERS, group=-2)
async def nonadmin_skip_vote(client, message):
    """Non-admin /skip: count as a vote instead of erroring with admin msg.

    Admins and sudoers pass straight through to the real /skip handler —
    this handler only intercepts to stop propagation for members lacking
    manage-video-chat rights.
    """
    chat_id = message.chat.id
    uid = message.from_user.id if message.from_user else 0
    if await _is_vc_admin(client, chat_id, uid):
        return

    check = db.get(chat_id)
    if not check:
        VS_VOTES.pop(chat_id, None)
        await reply_note(message, f"{pemoji('🔕')} ꜱᴋɪᴘ ꜰᴏʀ ᴡʜᴀᴛ? ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴇᴍᴘᴛʏ!")
        message.stop_propagation()

    title = str(check[0].get("title"))[:36]
    have, need, dup = await _cast_vote(chat_id, uid, title)
    if dup:
        await reply_note(message, f"ᴠᴏᴛᴇ ᴘᴇʜʟᴇ ꜱᴇ ᴄᴏᴜɴᴛᴇᴅ • ᴀʙ {have}/{need} ʜᴀʏ")
    elif have and have < need:
        await reply_note(message, f"ᴠᴏᴛᴇ ᴄᴏᴜɴᴛᴇᴅ • {have}/{need} ꜱᴋɪᴘ ɴᴇᴇᴅ ✅")
    elif have:
        VS_VOTES.pop(chat_id, None)
        await _run_vote_skip(chat_id, title, have)
    message.stop_propagation()
