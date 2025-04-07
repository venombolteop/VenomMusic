
# All rights reserved.
#

import asyncio
from datetime import datetime

from pyrogram.enums import ChatType

import config
from strings import get_string
from VenomX import app
from VenomX.core.call import Ayush
from VenomX.utils.database import (
    get_assistant,
    get_client,
    get_lang,
    is_active_chat,
    is_autoend,
)

autoend = {}



async def auto_end():
    if await is_autoend():
        await asyncio.sleep(30)
        for chat_id, timer in list(autoend.items()):
            if datetime.now() > timer:
                if not await is_active_chat(chat_id):
                    del autoend[chat_id]
                    continue

                userbot = await get_assistant(chat_id)
                members = []

                try:
                    async for member in userbot.get_call_members(chat_id):
                        if member is None:
                            continue
                        members.append(member)
                except ValueError:
                    try:
                        await Ayush.stop_stream(chat_id)
                    except Exception:
                        pass
                    continue

                if len(members) <= 1:
                    try:
                        await Ayush.stop_stream(chat_id)
                    except Exception:
                        pass

                    try:
                        language = await get_lang(message.chat.id)
                        language = get_string(language)
                    except Exception:
                        language = get_string("en")
                    try:
                        await app.send_message(
                            chat_id,
                            language["misc_1"],
                        )
                    except Exception:
                        pass

                del autoend[chat_id]


async def do_and_do():
    while True:
        await asyncio.gather(auto_end())
        await asyncio.sleep(1)


asyncio.create_task(do_and_do())
