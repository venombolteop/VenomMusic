# All rights reserved.

from typing import Union
from config import autoclean, chatstats, userstats
from config.config import time_to_seconds
from VenomX.misc import db


async def put_queue(
    chat_id: int,
    original_chat_id: int,
    file: str,
    title: str,
    duration: str,
    user: str,
    vidid: str,
    user_id: int,
    stream: str,
    url: str = None,
    forceplay: Union[bool, str] = False,
):
    # Normalize title
    title = title.title()

    # Convert duration safely
    try:
        duration_in_seconds = max(time_to_seconds(duration) - 3, 0)
    except Exception:
        duration_in_seconds = 0

    # Initialize queue if not exists
    if chat_id not in db:
        db[chat_id] = []

    # Normalize vidid
    if vidid in ("soundcloud", "saavn"):
        vidid = "telegram"

    # Song payload
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": duration_in_seconds,
        "played": 0,
        "url": url,
    }

    # Queue logic
    if forceplay and db[chat_id]:
        # Insert after currently playing track
        db[chat_id].insert(1, put)
    else:
        db[chat_id].append(put)

    # Auto clean temp files
    autoclean.append(file)

    # Chat stats
    if chat_id not in chatstats:
        chatstats[chat_id] = []

    chatstats[chat_id].append(
        {
            "vidid": vidid,
            "title": title,
        }
    )

    # User stats (DO NOT touch queue here)
    if user_id not in userstats:
        userstats[user_id] = []

    userstats[user_id].append(
        {
            "chat_id": chat_id,
            "title": title,
        }
    )

    # Return queue position
    return len(db[chat_id])
