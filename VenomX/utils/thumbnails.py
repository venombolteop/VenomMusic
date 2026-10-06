
# All rights reserved.
#

from py_yt import VideosSearch


async def gen_thumb(videoid, thumb=None):
    """A thumbnail for a video id.

    The direct URL is tried first and the search is only a fallback: a search
    costs a second or two per call, and this runs on every skip, where the
    music should already be playing before the picture is looked up.
    """
    if thumb:
        return thumb
    direct = f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"
    try:
        query = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(query, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail
    except Exception:
        return direct


async def gen_qthumb(vidid, thumb=None):
    if thumb:
        return thumb
    direct = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"
    try:
        query = f"https://www.youtube.com/watch?v={vidid}"
        results = VideosSearch(query, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail
    except Exception:
        return direct
