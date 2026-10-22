
# All rights reserved.
#
# Start module — rich-message cards (Bot API 10.3) + Venom branding.
#

import asyncio
import time

from py_yt import VideosSearch
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

import config
from config import BANNED_USERS, START_IMG_URL
from config.config import OWNER_ID
from strings import command, get_string
from VenomX import Platform, app
from VenomX.misc import SUDOERS, _boot_
from VenomX.plugins.bot.help import paginate_modules
from VenomX.plugins.play.playlist import del_plist_msg
from VenomX.plugins.sudo.sudoers import sudoers_list
from VenomX.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_assistant,
    get_lang,
    get_userss,
    is_on_off,
    is_served_private_chat,
)
from VenomX.utils.decorators.language import LanguageStart
from VenomX.utils.formatters import get_readable_time
from VenomX.utils.functions import MARKDOWN, WELCOMEHELP
from VenomX.utils.inline import private_panel, start_pannel
from VenomX.utils.rich_msg import (
    edit_rich,
    pemoji,
    rich_button,
    rich_button_row,
    rich_esc,
    rich_heading,
    rich_img,
    send_rich,
)

loop = asyncio.get_running_loop()


@app.on_message(command("START_COMMAND") & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_comm(client, message: Message, _):
    chat_id = message.chat.id
    await add_served_user(message.from_user.id)
    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]
        if name[0:4] == "help":
            body = rich_img(START_IMG_URL) if config.START_IMG_URL else ""
            body += rich_heading(f'{pemoji("🧮")} ᴠᴇɴᴏᴍ ɴᴇxᴜs ʜᴇʟᴘ', level=4)
            body += f"<p>{rich_esc(_['help_1'])}</p>"
            body += await paginate_modules(0, chat_id, close=True)
            return await send_rich(chat_id, body)
        if name[0:4] == "song":
            await message.reply_text(_["song_2"])
            return
        if name == "mkdwn_help":
            await send_rich(
                chat_id,
                rich_heading(f'{pemoji("🧾")} ᴛᴇxᴛ ꜰᴏʀᴍᴀᴛ ɴᴏᴛᴇꜱ', level=4)
                + f"<pre>{rich_esc(MARKDOWN)}</pre>",
            )
        if name == "greetings":
            await send_rich(
                chat_id,
                rich_heading(f'{pemoji("✨")} ᴇᴄᴏ-ᴡᴇʟᴄᴏᴍᴇ ᴠɪʙᴇꜱ', level=4)
                + f"<pre>{rich_esc(WELCOMEHELP)}</pre>",
            )
        if name[0:3] == "sta":
            mid = await send_rich(
                chat_id,
                rich_heading(f'{pemoji("⏳")} ᴄᴏʟʟᴇᴄᴛɪɴɢ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ...', level=4),
            )
            stats = await get_userss(message.from_user.id)
            tot = len(stats)
            if not stats:
                await asyncio.sleep(1)
                return await edit_rich(chat_id, mid, f"<p>{rich_esc(_['ustats_1'])}</p>")

            def get_stats():
                msg = ""
                limit = 0
                results = {}
                for i in stats:
                    top_list = stats[i]["spot"]
                    results[str(i)] = top_list
                    list_arranged = dict(
                        sorted(
                            results.items(),
                            key=lambda item: item[1],
                            reverse=True,
                        )
                    )
                if not results:
                    return None
                tota = 0
                videoid = None
                for vidid, count in list_arranged.items():
                    tota += count
                    if limit == 10:
                        continue
                    if limit == 0:
                        videoid = vidid
                    limit += 1
                    details = stats.get(vidid)
                    title = (details["title"][:35]).title()
                    if vidid == "telegram":
                        msg += f"{pemoji('🔗')} ᴛᴇʟᴇɢʀᴀᴍ ꜰɪʟᴇꜱ  {count}x \n"
                    else:
                        msg += f"{pemoji('🔗')} {rich_esc(title)}  {count}x \n"
                msg = rich_esc(_["ustats_2"].format(tot, tota, limit)) + msg
                return videoid, msg

            try:
                got = await loop.run_in_executor(None, get_stats)
            except Exception as e:
                print(e)
                return
            if got is None:
                return await edit_rich(chat_id, mid, f"<p>{rich_esc(_['ustats_1'])}</p>")
            videoid, msg = got
            thumbnail = await Platform.youtube.thumbnail(videoid, True)
            body = rich_img(thumbnail)
            body += rich_heading(f'{pemoji("📊")} ᴠᴇɴᴏᴍ ᴘᴇʀꜱᴏɴᴀʟ ꜱᴛᴀᴛꜱ', level=4)
            body += f"<p>{msg}</p>"
            await edit_rich(chat_id, mid, body)
            return
        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            await asyncio.sleep(1)
            if await is_on_off(config.LOG):
                sender_id = message.from_user.id
                sender_mention = message.from_user.mention
                sender_name = message.from_user.first_name
                return await app.send_message(
                    config.LOGGER_ID,
                    f"{message.from_user.mention} Has just started bot to check <code>Sudolist </code>\n\n**User Id:** {sender_id}\n**User Name:** {sender_name}",
                )
            return
        if name[0:3] == "lyr":
            query = (str(name)).replace("lyrics_", "", 1)
            lyrical = config.lyrical
            lyrics = lyrical.get(query)
            if lyrics:
                await Platform.telegram.send_split_text(message, lyrics)
                return
            else:
                await message.reply_text("Failed to get lyrics ")
                return
        if name[0:3] == "del":
            await del_plist_msg(client=client, message=message, _=_)
            await asyncio.sleep(1)
        if name[0:3] == "inf":
            mid = await send_rich(
                chat_id,
                rich_heading(f'{pemoji("⏳")} ᴄᴏʟʟᴇᴄᴛɪɴɢ ɪɴꜰᴏ...', level=4),
            )
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            results = VideosSearch(query, limit=1)
            for result in (await results.next())["result"]:
                title = result["title"]
                duration = result["duration"]
                views = result["viewCount"]["short"]
                thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                channellink = result["channel"]["link"]
                channel = result["channel"]["name"]
                link = result["link"]
                published = result["publishedTime"]
            body = rich_img(thumbnail)
            body += rich_heading(f'{pemoji("🔍")} ᴠᴇɴᴏᴍ ᴛʀᴀᴄᴋ ɪɴꜰᴏ', level=4)
            body += (
                f"<p><b>{rich_esc(title)}</b></p>"
                f"<p>{pemoji('⏳')} <b>ᴅᴜʀᴀᴛɪᴏɴ</b>: {rich_esc(duration)} ᴍɪɴꜱ\n"
                f"{pemoji('👀')} <b>ᴠɪᴇᴡꜱ</b>: {rich_esc(views)}\n"
                f"{pemoji('⏰')} <b>ᴘᴜʙʟɪꜱʜᴇᴅ</b>: {rich_esc(published)}\n"
                f"{pemoji('🎥')} <b>ᴄʜᴀɴɴᴇʟ</b>: {rich_esc(channel)}</p>"
            )
            body += rich_button_row(
                rich_url_button(f"{pemoji('👀')} ᴡᴀᴛᴄʜ ᴏɴ ʏᴏᴜᴛᴜʙᴇ", link, style="primary"),
                rich_button(f"{pemoji('❌')} ᴄʟᴏꜱᴇ", callback_data="close", style="danger"),
            )
            await edit_rich(chat_id, mid, body)
            await asyncio.sleep(1)
            if await is_on_off(config.LOG):
                sender_id = message.from_user.id
                sender_name = message.from_user.first_name
                return await app.send_message(
                    config.LOGGER_ID,
                    f"🚀 {message.from_user.mention} Has just started bot ot check <code> Video information  </code>\n\n👤 **User Id:** {sender_id}\n**User Name** {sender_name}",
                )
    else:
        try:
            await app.resolve_peer(OWNER_ID[0])
            OWNER = OWNER_ID[0]
        except Exception:
            OWNER = None
        out = private_panel(_, app.username, OWNER)
        body = rich_img(START_IMG_URL) if config.START_IMG_URL else ""
        body += rich_heading(f'{pemoji("🎧")} ᴠᴇɴᴏᴍ ᴍᴜꜱɪᴄ ʜᴜʙ', level=4)
        body += f"<p>{rich_esc(_['start_1'].format(app.mention))}</p>"
        body += out
        await send_rich(chat_id, body)

        if await is_on_off(config.LOG):
            sender_id = message.from_user.id
            sender_name = message.from_user.first_name
            return await app.send_message(
                config.LOGGER_ID,
                f"👋 {message.from_user.mention} Has started bot. \n\n🆔 **User id :** {sender_id}\n**User name:** {sender_name}",
            )


@app.on_message(command("START_COMMAND") & filters.group & ~BANNED_USERS)
@LanguageStart
async def testbot(client, message: Message, _):
    uptime = int(time.time() - _boot_)
    chat_id = message.chat.id
    await message.reply_text(_["start_7"].format(get_readable_time(uptime)))

    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    chat_id = message.chat.id
    if config.PRIVATE_BOT_MODE == str(True):
        if not await is_served_private_chat(message.chat.id):
            await message.reply_text(
                "**ᴛʜɪꜱ ʙᴏᴛ'ꜱ ᴘʀɪᴠᴀᴛᴇ ᴍᴏᴅᴇ ʜᴀꜱ ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ ᴏɴʟʏ ᴍʏ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ ɪꜰ ᴡᴀɴᴛ ᴛᴏ ᴜꜱᴇ ᴛʜɪꜱ ɪɴ ʏᴏᴜʀ ᴄʜᴀᴛ ꜱᴏ ꜱᴀʏ ᴛᴏ ᴍʏ ᴏᴡɴᴇʀ ᴛᴏ ᴀᴜᴛʜᴏʀɪᴢᴇ ʏᴏᴜʀ ᴄʜᴀᴛ."
            )
            return await app.leave_chat(message.chat.id)
    else:
        await add_served_chat(chat_id)
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
            if member.id == app.id:
                chat_type = message.chat.type
                if chat_type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_5"])
                    return await app.leave_chat(message.chat.id)
                if chat_id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_6"].format(
                            f"https://t.me/{app.username}?start=sudolist"
                        )
                    )
                    return await app.leave_chat(chat_id)
                userbot = await get_assistant(message.chat.id)
                out = start_pannel(_)
                body = rich_heading(f'{pemoji("🎧")} ᴠᴇɴᴏᴍ ᴀʀʀɪᴠᴇᴅ ɪɴ ᴠɪʙᴇ!', level=4)
                body += f"<p>{rich_esc(_['start_2'].format(app.mention, userbot.username, userbot.id))}</p>"
                body += out
                await send_rich(chat_id, body)
            if member.id in config.OWNER_ID:
                return await message.reply_text(
                    _["start_3"].format(app.mention, member.mention)
                )
            if member.id in SUDOERS:
                return await message.reply_text(
                    _["start_4"].format(app.mention, member.mention)
                )
            return
        except:

            return
