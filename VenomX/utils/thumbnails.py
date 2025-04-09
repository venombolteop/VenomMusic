
# All rights reserved.
#

from py_yt import VideosSearch


async def gen_thumb(videoid, thumb=None):
    if thumb:
        return thumb
    try:
        query = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(query, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail
    except Exception as e:
        return f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"


async def gen_qthumb(vidid, thumb=None):
    if thumb:
        return thumb
    try:
        query = f"https://www.youtube.com/watch?v={vidid}"
        results = VideosSearch(query, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail
    except Exception as e:
        return f"https://img.youtube.com/vi/{vidid}/maxresdefault.jpg"
