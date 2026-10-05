# All rights reserved.
#

import re

import aiohttp
from bs4 import BeautifulSoup
from py_yt import VideosSearch

UA = (
    "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Mobile Safari/537.36"
)


class Resso:
    def __init__(self):
        self.regex = r"^(https?:\/\/)(m\.|www\.)?resso\.com\/(.*)$"
        self.base = "https://m.resso.com/"

    async def valid(self, link: str):
        if re.search(self.regex, link):
            return True
        else:
            return False

    def _query_from_url(self, url: str):
        path = re.sub(r"^https?://(m\.|www\.)?resso\.com/", "", url.split("?")[0])
        slug = path.split("/")[1] if path.count("/") > 1 else ""
        slug = re.sub(r"[-_]+", " ", slug).strip()
        return slug

    async def track(self, url, playid: bool | str = None):
        if playid:
            url = self.base + url
        search = None
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": UA}) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        for tag in soup.find_all("meta"):
                            if tag.get("property", None) == "og:title":
                                search = tag.get("content", None)
                            if tag.get("property", None) == "og:description":
                                des = tag.get("content", None) or ""
                                try:
                                    des = des.split("·")[0]
                                except Exception:
                                    pass
                        if not des.strip():
                            search = None
        except Exception:
            search = None

        if not search:
            search = self._query_from_url(url)
        if not search:
            return False

        results = VideosSearch(search, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            ytlink = result["link"]
            vidid = result["id"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": ytlink,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid