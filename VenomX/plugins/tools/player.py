
# All rights reserved.
#

from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from VenomX import app
from VenomX.misc import db
from VenomX.utils.decorators import AdminRightsCheck
from VenomX.utils.rich_msg import send_note
from VenomX.utils.rich_panels import snapshot_card


@app.on_message(
    filters.command(["cplayer", "playing", "cplaying", "player"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def pause_admin(cli, message: Message, _, chat_id):
    check = db.get(chat_id)
    playing = check[0] if check else {}

    if playing.get("markup") == "rich":
        mid = await snapshot_card(chat_id)
        if mid:
            return

    _thumbs_obj = next(
        (
            item["mystic"].photo.thumbs
            for item in check
            if isinstance(item, dict)
            and "mystic" in item
            and hasattr(item["mystic"].photo, "thumbs")
        ),
        None,
    )
    thumbs = _thumbs_obj[0].file_id if _thumbs_obj else None
    caption = next(
        (
            item["mystic"].caption
            for item in check
            if isinstance(item, dict)
            and "mystic" in item
            and hasattr(item["mystic"], "caption")
        ),
        None,
    )
    if not thumbs:
        await send_note(chat_id, "No active track to mirror right now.")
        return

    await message.reply_photo(
        photo=thumbs, caption=caption, reply_markup=reply_markup, has_spoiler=True
    )
