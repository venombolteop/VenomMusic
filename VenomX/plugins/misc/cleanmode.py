import asyncio
from datetime import datetime, timedelta

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait
from pyrogram.raw import types

import config
from config import adminlist, chatstats, clean, userstats
from VenomX import app, userbot
from VenomX.misc import SUDOERS
from VenomX.utils.database import (get_active_chats,
                                       get_authuser_names, get_client,
                                       
 get_served_chats,
 get_served_users, is_cleanmode_on, set_queries)
                                       
from VenomX.utils.decorators.language import language
from VenomX.utils.formatters import alpha_to_int

AUTO_DELETE = config.CLEANMODE_DELETE_MINS
AUTO_SLEEP = 5
IS_BROADCASTING = False
cleanmode_group = 15


@app.on_raw_update(group=cleanmode_group)
async def clean_mode(client, update, users, chats):
    global IS_BROADCASTING
    if IS_BROADCASTING:
        return
    try:
        if not isinstance(update, types.UpdateReadChannelOutbox):
            return
    except:
        return
    if users:
        return
    if chats:
        return
    message_id = update.max_id
    chat_id = int(f"-100{update.channel_id}")
    if not await is_cleanmode_on(chat_id):
        return
    if chat_id not in clean:
        clean[chat_id] = []
    time_now = datetime.now()
    put = {
        "msg_id": message_id,
        "timer_after": time_now + timedelta(minutes=AUTO_DELETE),
    }
    clean[chat_id].append(put)
    await set_queries(1)



async def auto_clean():
    while not await asyncio.sleep(AUTO_SLEEP):
        try:
            for chat_id in chatstats:
                for dic in chatstats[chat_id]:
                    vidid = dic["vidid"]
                    title = dic["title"]
                    chatstats[chat_id].pop(0)
            for user_id in userstats:
                for dic in userstats[user_id]:
                    vidid = dic["vidid"]
                    title = dic["title"]
                    userstats[user_id].pop(0)
        except:
            continue
        try:
            for chat_id in clean:
                if chat_id == config.LOGGER_ID:
                    continue
                for x in clean[chat_id]:
                    if datetime.now() > x["timer_after"]:
                        try:
                            await app.delete_messages(
                                chat_id, x["msg_id"]
                            )
                        except FloodWait as e:
                            await asyncio.sleep(e.value)
                        except:
                            continue
                    else:
                        continue
        except:
            continue
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    admins = (
                        app.get_chat_members(
                            chat_id, 
                            filter=ChatMembersFilter.ADMINISTRATORS
                        )
                    ).privileges
                    async for user in admins:
                        if user.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue


asyncio.create_task(auto_clean())
