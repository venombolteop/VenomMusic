
# All rights reserved.
#
# Stats module — rich-message cards (Bot API 10.3) + Venom branding.
#

import asyncio
import platform
from sys import version as pyver

import psutil
from pyrogram import __version__ as pyrover
from pyrogram import filters
from pyrogram.types import CallbackQuery
from pytgcalls.__version__ import __version__ as pytgver

import config
from config import BANNED_USERS
from strings import command
from VenomX import Platform, app
from VenomX.core.userbot import assistants
from VenomX.misc import SUDOERS, pymongodb
from VenomX.plugins import ALL_MODULES
from VenomX.utils.database import (
    get_global_tops,
    get_particulars,
    get_queries,
    get_served_chats,
    get_served_users,
    get_sudoers,
    get_top_chats,
    get_topp_users,
)
from VenomX.utils.decorators.language import language, languageCB
from VenomX.utils.inline.stats import (
    back_stats_buttons,
    back_stats_markup,
    get_stats_markup,
    overallback_stats_markup,
    stats_buttons,
    top_ten_stats_markup,
)
from VenomX.utils.rich_msg import (
    edit_rich,
    pemoji,
    rich_esc,
    rich_heading,
    rich_img,
    send_rich,
)

loop = asyncio.get_running_loop()


@app.on_message(command("STATS_COMMAND") & ~BANNED_USERS)
@language
async def stats_global(client, message, _):
    upl = stats_buttons(_, True if message.from_user.id in SUDOERS else False)
    body = rich_img(config.STATS_IMG_URL)
    body += rich_heading(f'{pemoji("📊")} ᴠᴇɴᴏᴍ sᴛᴀᴛs', level=4)
    body += f"<p>{rich_esc(_['gstats_11'].format(app.mention))}</p>"
    body += upl
    await send_rich(message.chat.id, body)


@app.on_message(command("GSTATS_COMMAND") & ~BANNED_USERS)
@language
async def gstats_global(client, message, _):
    mystic = await send_rich(
        message.chat.id, f"<p>{rich_esc(_['gstats_1'])}</p>"
    )
    stats = await get_global_tops()
    if not stats:
        await asyncio.sleep(1)
        return await edit_rich(message.chat.id, mystic, f"<p>{rich_esc(_['gstats_2'])}</p>")

    def get_stats():
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
        videoid = None
        co = None
        for vidid, count in list_arranged.items():
            if vidid == "telegram":
                continue
            else:
                videoid = vidid
                co = count
            break
        return videoid, co

    try:
        videoid, co = await loop.run_in_executor(None, get_stats)
    except Exception as e:
        print(e)
        return
    if videoid is None:
        return await edit_rich(message.chat.id, mystic, f"<p>{rich_esc(_['gstats_2'])}</p>")
    (
        title,
        duration_min,
        duration_sec,
        thumbnail,
        vidid,
    ) = await Platform.youtube.details(videoid, True)
    title = title.title()
    upl = get_stats_markup(_, True if message.from_user.id in SUDOERS else False)
    body = rich_img(thumbnail)
    body += rich_heading(f'{pemoji("🏆")} ᴛᴏᴘ ᴘʟᴀʏᴇᴅ ᴛʀᴀᴄᴋ', level=4)
    body += (
        f"<p><b>{rich_esc(title)}</b></p>"
        f"<p>{pemoji('🔥')} {rich_esc(app.mention)} — {rich_esc(co)}x</p>"
    )
    body += upl
    await edit_rich(message.chat.id, mystic, body)


@app.on_callback_query(filters.regex("GetStatsNow") & ~BANNED_USERS)
@languageCB
async def top_users_ten(client, CallbackQuery: CallbackQuery, _):
    chat_id = CallbackQuery.message.chat.id
    callback_data = CallbackQuery.data.strip()
    what = callback_data.split(None, 1)[1]
    upl = back_stats_markup(_)
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    chat_id_cb = CallbackQuery.message.chat.id
    mid = CallbackQuery.message.id
    sub = f"ᴏғ {rich_esc(CallbackQuery.message.chat.title)}" if what == "Here" else what
    await edit_rich(
        chat_id_cb,
        mid,
        rich_heading(f'{pemoji("⏳")} ᴄᴏʟʟᴇᴄᴛɪɴɢ {sub}...', level=4),
    )
    if what == "Tracks":
        stats = await get_global_tops()
    elif what == "Chats":
        stats = await get_top_chats()
    elif what == "Users":
        stats = await get_topp_users()
    elif what == "Here":
        stats = await get_particulars(chat_id)
    if not stats:
        await asyncio.sleep(1)
        return await edit_rich(
            chat_id_cb, mid, f"<p>{rich_esc(_['gstats_2'])}</p>{upl}"
        )
    queries = await get_queries()

    def get_stats():
        results = {}
        for i in stats:
            top_list = stats[i] if what in ["Chats", "Users"] else stats[i]["spot"]
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
        msg = ""
        limit = 0
        total_count = 0
        if what in ["Tracks", "Here"]:
            for items, count in list_arranged.items():
                total_count += count
                if limit == 10:
                    continue
                limit += 1
                details = stats.get(items)
                title = (details["title"][:35]).title()
                if items == "telegram":
                    msg += f"📁 ᴛᴇʟᴇɢʀᴀᴍ ꜰɪʟᴇꜱ  {count}x \n"
                else:
                    msg += f" {rich_esc(title)}  {count}x \n"
            temp = (
                _["gstats_4"].format(
                    queries,
                    app.mention,
                    len(stats),
                    total_count,
                    limit,
                )
                if what == "Tracks"
                else _["gstats_7"].format(len(stats), total_count, limit)
            )
            msg = temp + msg
        return msg, list_arranged

    try:
        got = await loop.run_in_executor(None, get_stats)
    except Exception as e:
        print(e)
        return
    if got is None:
        return await edit_rich(
            chat_id_cb, mid, f"<p>{rich_esc(_['gstats_2'])}</p>{upl}"
        )
    msg, list_arranged = got
    limit = 0
    if what in ["Users", "Chats"]:
        for items, count in list_arranged.items():
            if limit == 10:
                break
            try:
                extract = (
                    (await app.get_users(items)).first_name
                    if what == "Users"
                    else (await app.get_chat(items)).title
                )
                if extract is None:
                    continue
                await asyncio.sleep(0.5)
            except Exception:
                continue
            limit += 1
            msg += f" {rich_esc(extract)}  {count}x \n"
        temp = (
            _["gstats_5"].format(limit, app.mention)
            if what == "Chats"
            else _["gstats_6"].format(limit, app.mention)
        )
        msg = temp + msg
    body = rich_img(config.GLOBAL_IMG_URL)
    body += rich_heading(f'{pemoji("📊")} ᴠᴇɴᴏᴍ ᴛᴏᴘ ʟɪsᴛ', level=4)
    body += f"<p>{msg}</p>"
    body += upl
    await edit_rich(chat_id_cb, mid, body)


@app.on_callback_query(filters.regex("TopOverall") & ~BANNED_USERS)
@languageCB
async def overall_stats(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    what = callback_data.split(None, 1)[1]
    if what != "s":
        upl = overallback_stats_markup(_)
    else:
        upl = back_stats_buttons(_)
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    served_chats = len(await get_served_chats())
    served_users = len(await get_served_users())
    total_queries = await get_queries()
    blocked = len(BANNED_USERS)
    sudoers = len(SUDOERS)
    mod = len(ALL_MODULES)
    assistant = len(assistants)
    playlist_limit = config.SERVER_PLAYLIST_LIMIT
    fetch_playlist = config.PLAYLIST_FETCH_LIMIT
    song = config.SONG_DOWNLOAD_DURATION
    play_duration = config.DURATION_LIMIT_MIN
    if config.AUTO_LEAVING_ASSISTANT == str(True):
        ass = "Yes"
    else:
        ass = "No"
    body = rich_img(config.STATS_IMG_URL)
    body += rich_heading(f'{pemoji("📊")} ᴠᴇɴᴏᴍ ʙᴏᴛ sᴛᴀᴛs', level=4)
    body += (
        f"<p>🧬 ᴍᴏᴅᴜʟᴇꜱ: {mod}</p>"
        f"<p>🛸 ꜱᴇʀᴠᴇᴅ ᴄʜᴀᴛꜱ: {served_chats}</p>"
        f"<p>👤 ꜱᴇʀᴠᴇᴅ ᴜꜱᴇʀꜱ: {served_users}</p>"
        f"<p>🚫 ʙʟᴏᴄᴋᴇᴅ ᴜꜱᴇʀꜱ: {blocked}</p>"
        f"<p>👑 ꜱᴜᴅᴏ ᴜꜱᴇʀꜱ: {sudoers}</p>"
        f"<p>❤️ ᴛᴏᴛᴀʟ qᴜᴇʀɪᴇꜱ: {total_queries}</p>"
        f"<p>💌 ᴀꜱꜱɪꜱᴛᴀɴᴛꜱ: {assistant}</p>"
        f"<p>🚀 ᴀᴜᴛᴏ ʟᴇᴀᴠɪɴɢ: {ass}</p>"
        f"<p>⏱ ᴘʟᴀʏ ʟɪᴍɪᴛ: {play_duration} ᴍɪɴꜱ</p>"
        f"<p>💠 ᴄʟᴇᴀɴ ꜱᴏɴɢ ʟɪᴍ: {song} ᴍɪɴꜱ</p>"
        f"<p>📕 ᴘʟᴀʏʟɪꜱᴛ ʟɪᴍ: {playlist_limit} / {fetch_playlist}</p>"
    )
    body += upl
    await edit_rich(CallbackQuery.message.chat.id, CallbackQuery.message.id, body)


@app.on_callback_query(filters.regex("bot_stats_sudo"))
@languageCB
async def overall_stats(client, CallbackQuery, _):
    if CallbackQuery.from_user.id not in SUDOERS:
        return await CallbackQuery.answer("ᴏɴʟʏ ꜰᴏʀ ꜱᴜᴅᴏ ᴜꜱᴇʀ'ꜱ", show_alert=True)
    callback_data = CallbackQuery.data.strip()
    what = callback_data.split(None, 1)[1]
    if what != "s":
        upl = overallback_stats_markup(_)
    else:
        upl = back_stats_buttons(_)
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    sc = platform.system()
    p_core = psutil.cpu_count(logical=False)
    t_core = psutil.cpu_count(logical=True)
    ram = str(round(psutil.virtual_memory().total / (1024.0**3))) + " GB"
    try:
        cpu_freq = psutil.cpu_freq().current
        if cpu_freq >= 1000:
            cpu_freq = f"{round(cpu_freq / 1000, 2)}GHz"
        else:
            cpu_freq = f"{round(cpu_freq, 2)}MHz"
    except Exception:
        cpu_freq = "ᴇʀʀᴏʀ"
    hdd = psutil.disk_usage("/")
    total = hdd.total / (1024.0**3)
    total = str(total)
    used = hdd.used / (1024.0**3)
    used = str(used)
    free = hdd.free / (1024.0**3)
    free = str(free)
    mod = len(ALL_MODULES)
    db = pymongodb
    call = db.command("dbstats")
    datasize = call["dataSize"] / 1024
    datasize = str(datasize)
    storage = call["storageSize"] / 1024
    objects = call["objects"]
    collections = call["collections"]

    served_chats = len(await get_served_chats())
    served_users = len(await get_served_users())
    total_queries = await get_queries()
    blocked = len(BANNED_USERS)
    sudoers = len(await get_sudoers())
    body = rich_img(config.STATS_IMG_URL)
    body += rich_heading(f'{pemoji("🖥")} ᴠᴇɴᴏᴍ ꜱᴜᴅᴏ ꜱᴛᴀᴛꜱ', level=4)
    body += (
        f"<p>🧬 ᴍᴏᴅᴜʟᴇꜱ: {mod}</p>"
        f"<p>🛡 ᴘʟᴀᴛꜰᴏʀᴍ: {rich_esc(sc)}</p>"
        f"<p>💾 ʀᴀᴍ: {rich_esc(ram)}</p>"
        f"<p>⚙ ᴄᴏʀᴇꜱ: {p_core} / {t_core}</p>"
        f"<p>⏩ ᴄᴘᴜ: {rich_esc(cpu_freq)}</p>"
        f"<p>🐍 ᴘʏᴛʜᴏɴ: {rich_esc(pyver.split()[0])}</p>"
        f"<p>🚩 ᴘʏʀᴏɢʀᴀᴍ: {rich_esc(pyrover)}</p>"
        f"<p>📞 ᴘʏ-ᴛɢᴄᴀʟʟꜱ: {rich_esc(pytgver)}</p>"
        f"<p>🌩 ꜱᴛᴏʀᴇᴅ: {rich_esc(total[:4])} ɢɪʙ / {rich_esc(used[:4])} / {rich_esc(free[:4])}</p>"
        f"<p>🛸 ᴄʜᴀᴛꜱ: {served_chats} 👤 ᴜꜱᴇʀꜱ: {served_users}</p>"
        f"<p>❤️ qᴜᴇʀɪᴇꜱ: {total_queries}</p>"
        f"<p>🗂 ᴅʙ: {rich_esc(storage)} ᴍʙ · {collections} ᴄᴏʟ · {objects} ᴋᴇʏꜱ</p>"
    )
    body += upl
    await edit_rich(CallbackQuery.message.chat.id, CallbackQuery.message.id, body)


@app.on_callback_query(
    filters.regex(pattern=r"^(TOPMARKUPGET|GETSTATS|GlobalStats)$") & ~BANNED_USERS
)
@languageCB
async def back_buttons(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    command = CallbackQuery.matches[0].group(1)
    chat_id = CallbackQuery.message.chat.id
    mid = CallbackQuery.message.id
    if command == "TOPMARKUPGET":
        body = rich_img(config.GLOBAL_IMG_URL)
        body += rich_heading(f'{pemoji("📊")} ᴛᴏᴘ ꜱᴛᴀᴛꜱ ᴠɪᴇᴡ', level=4)
        body += f"<p>{rich_esc(_['gstats_9'])}</p>"
        body += top_ten_stats_markup(_)
        await edit_rich(chat_id, mid, body)
    if command == "GlobalStats":
        body = rich_img(config.GLOBAL_IMG_URL)
        body += rich_heading(f'{pemoji("📊")} ꜰᴜʟʟ ꜱᴛᴀᴛꜱ ᴢᴏɴᴇ', level=4)
        body += (
            f"<p>{rich_esc(_['gstats_10'].format(app.mention))}</p>"
            + get_stats_markup(
                _,
                True if CallbackQuery.from_user.id in SUDOERS else False,
            )
        )
        await edit_rich(chat_id, mid, body)
    if command == "GETSTATS":
        body = rich_img(config.STATS_IMG_URL)
        body += rich_heading(f'{pemoji("📊")} ꜰᴜʟʟ ꜱᴛᴀᴛꜱ ᴢᴏɴᴇ', level=4)
        body += (
            f"<p>{rich_esc(_['gstats_11'].format(app.mention))}</p>"
            + stats_buttons(
                _,
                True if CallbackQuery.from_user.id in SUDOERS else False,
            )
        )
        await edit_rich(chat_id, mid, body)
