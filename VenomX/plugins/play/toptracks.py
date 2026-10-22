
# All rights reserved.
#
# Top-tracks module — rich-message panels (Bot API 10.3) + Venom branding.
#

import asyncio

from pyrogram import filters

from config import BANNED_USERS
from strings import get_string
from VenomX import app
from VenomX.utils.database import (
    get_global_tops,
    get_particulars,
    get_userss,
)
from VenomX.utils.decorators import languageCB
from VenomX.utils.inline.playlist import (
    botplaylist_markup,
    failed_top_markup,
    top_play_markup,
)
from VenomX.utils.rich_msg import (
    RichMystic,
    delete_msg,
    edit_rich,
    pemoji,
    rich_esc,
    rich_heading,
    send_rich,
)
from VenomX.utils.stream.stream import stream

loop = asyncio.get_running_loop()


@app.on_callback_query(filters.regex("get_playmarkup") & ~BANNED_USERS)
@languageCB
async def get_play_markup(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    await edit_rich(
        CallbackQuery.message.chat.id,
        CallbackQuery.message.id,
        rich_heading(f'{pemoji("🎵")} ᴘʟᴀʏʟɪsᴛ ᴍᴇɴᴜ', level=4)
        + botplaylist_markup(_),
    )


@app.on_callback_query(filters.regex("get_top_playlists") & ~BANNED_USERS)
@languageCB
async def get_topz_playlists(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    await edit_rich(
        CallbackQuery.message.chat.id,
        CallbackQuery.message.id,
        rich_heading(f'{pemoji("🔥")} ᴛᴏᴘ ᴘʟᴀʏʟɪsᴛ ᴇᴅɪᴛᴏʀ', level=4)
        + top_play_markup(_),
    )


@app.on_callback_query(filters.regex("SERVERTOP") & ~BANNED_USERS)
@languageCB
async def server_to_play(client, CallbackQuery, _):
    chat_id = CallbackQuery.message.chat.id
    user_name = CallbackQuery.from_user.first_name
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    callback_data = CallbackQuery.data.strip()
    what = callback_data.split(None, 1)[1]
    mid = await send_rich(
        chat_id,
        rich_heading(
            f'{pemoji("⏳")} ᴄᴏᴍᴘɪʟɪɴɢ {rich_esc(what)} ᴛᴏᴘ ʟɪsᴛ ᴏꜰ {rich_esc(CallbackQuery.from_user.first_name)}...',
            level=4,
        ),
    )
    if not mid:
        return
    if what == "Global":
        stats = await get_global_tops()
    elif what == "Group":
        stats = await get_particulars(chat_id)
    elif what == "Personal":
        stats = await get_userss(CallbackQuery.from_user.id)
    if not stats:
        return await edit_rich(
            chat_id,
            mid,
            f"<p>{rich_esc(_['tracks_2'].format(what))}</p>"
            + failed_top_markup(_),
        )

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
        details = []
        limit = 0
        for vidid, count in list_arranged.items():
            if vidid == "telegram":
                continue
            if limit == 10:
                break
            limit += 1
            details.append(vidid)
        if not details:
            return None
        return details

    try:
        details = await loop.run_in_executor(None, get_stats)
    except Exception as e:
        print(e)
        return
    if details is None:
        return await edit_rich(
            chat_id,
            mid,
            f"<p>{rich_esc(_['tracks_2'].format(what))}</p>"
            + failed_top_markup(_),
        )
    try:
        await stream(
            _,
            RichMystic(chat_id, mid),
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video=False,
            streamtype="playlist",
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_3"].format(ex_type)
        return await edit_rich(chat_id, mid, f"<p>{rich_esc(err)}</p>")
    return await delete_msg(chat_id, mid)
