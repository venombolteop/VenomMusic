#
#  VenomX - An Opensource Python Telegram Bot Audio/Video Player.
#  Copyright (C) 2021 - 2026  <@venombolteop>
#  All rights reserved.
#

from py_yt import VideosSearch

from VenomX.utils.rich_msg import url_ok


async def _pick(videoid):
    """maxresdefault when it exists, else the search thumbnail, else hqdefault."""
    direct = f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"
    if await url_ok(direct):
        return direct
    fallback = f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"
    try:
        query = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(query, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail
    except Exception:
        return fallback


async def gen_thumb(videoid, thumb=None):
    """A thumbnail for a video id.

    maxresdefault is preferred; the search is only a fallback: a search
    costs a second or two per call, and this runs on every skip, where the
    music should already be playing before the picture is looked up.
    """
    if thumb:
        return thumb
    return await _pick(videoid)


async def gen_qthumb(vidid, thumb=None):
    if thumb:
        return thumb
    return await _pick(vidid)
