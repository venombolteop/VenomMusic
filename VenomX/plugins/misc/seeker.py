
# All rights reserved.
#
import asyncio

from pyrogram.types import InlineKeyboardMarkup

from strings import get_string
from VenomX.core.call import Ayush
from VenomX.utils.stream.playback import current
from VenomX.misc import db
from VenomX.utils.database import (
    get_active_chats,
    get_lang,
    is_music_playing,
)
from VenomX.utils.formatters import seconds_to_min
from VenomX.utils.inline import stream_markup_timer, telegram_markup_timer

from ..admins.callback import wrong


async def timer():
    while True:
        await asyncio.sleep(1)
        for chat_id, source in list(current.items()):
            queue = db.get(chat_id)
            if queue and queue[0].get("seconds"):
                queue[0]["played"] = min(int(source.position()), queue[0]["seconds"])


async def markup_timer():
    while True:
        await asyncio.sleep(2)
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            if Ayush.is_join_pending(chat_id):
                continue

            if not await is_music_playing(chat_id):
                continue

            playing = db.get(chat_id)
            if not playing:
                continue

            duration_seconds = int(playing[0]["seconds"])

            try:
                language = await get_lang(chat_id)
                _ = get_string(language)
            except Exception:
                _ = get_string("en")

            if duration_seconds == 0:
                continue

            try:
                mystic = playing[0]["mystic"]
                markup = playing[0]["markup"]
            except Exception:
                continue

            try:
                check = wrong[chat_id][mystic.id]
                if check is False:
                    continue
            except Exception:
                pass

            if markup == "rich":
                continue

            try:
                buttons = (
                    stream_markup_timer(
                        _,
                        playing[0]["vidid"],
                        chat_id,
                        seconds_to_min(playing[0]["played"]),
                        playing[0]["dur"],
                    )
                    if markup == "stream"
                    else telegram_markup_timer(
                        _,
                        chat_id,
                        seconds_to_min(playing[0]["played"]),
                        playing[0]["dur"],
                    )
                )

                await mystic.edit_reply_markup(
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            except Exception:
                continue


asyncio.create_task(timer(), name="timer")
asyncio.create_task(markup_timer(), name="markup_timer")
