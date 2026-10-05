# All rights reserved.
#

import json
import random
import re
import time

import requests
from py_yt import VideosSearch

from VenomX.utils.decorators import asyncify

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
EMBED = "https://open.spotify.com/embed/{}/{}"
NEXT_DATA = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
FETCH_TIMEOUT = 20
CACHE_TTL = 900


class Spotify:
    """Auth-free Spotify resolver built on the public embed payload.

    Supports tracks, albums, artists, artist radio and playlists without any
    API key, so the bot keeps working when the client-credentials quota
    is exhausted.
    """

    def __init__(self):
        self.regex = r"^(https?:\/\/)(open|play)\.spotify\.com\/(.*)$"
        self._cache = {}

    async def valid(self, link: str):
        if re.search(self.regex, link):
            return True
        else:
            return False

    def _parse(self, link: str):
        path = re.split(r"^(?:https?://)(?:open|play)\.spotify\.com/", link)[-1]
        path = path.split("?")[0].split("#")[0].strip("/")
        if not path:
            raise ValueError("Invalid Spotify link")
        parts = path.split("/")
        kind = parts[0].lower()
        if kind in ("intl", "embed"):
            parts = parts[2:] if len(parts) > 2 else parts
            kind = parts[0].lower() if parts else ""
        if kind not in ("track", "album", "artist", "playlist"):
            raise ValueError(f"Unsupported Spotify link: {kind}")
        entity_id = parts[1]
        radio = "radio" in parts[2:]
        return kind, entity_id, radio

    @asyncify
    def _fetch_entity(self, kind: str, entity_id: str) -> dict:
        cached = self._cache.get((kind, entity_id))
        if cached and cached[0] > time.time():
            return cached[1]
        response = requests.get(
            EMBED.format(kind, entity_id), headers={"User-Agent": UA}, timeout=FETCH_TIMEOUT
        )
        response.raise_for_status()
        match = re.search(NEXT_DATA, response.text, re.S)
        if not match:
            raise ValueError(f"Spotify {kind} not found: {entity_id}")
        payload = json.loads(match.group(1))
        entity = (
            payload.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity")
        )
        if not entity:
            raise ValueError(f"Spotify {kind} not found: {entity_id}")
        self._cache[(kind, entity_id)] = (time.time() + CACHE_TTL, entity)
        return entity

    async def _entity(self, link: str):
        kind, entity_id, radio = self._parse(link)
        entity = await self._fetch_entity(kind, entity_id)
        return kind, entity_id, radio, entity

    @staticmethod
    def _cover(entity: dict):
        for source in (entity.get("coverArt") or {}).get("sources", []):
            if source.get("url"):
                return source["url"].split("?")[0]
        return ""

    async def _youtube_details(self, info: str):
        results = VideosSearch(info, limit=1)
        for result in (await results.next())["result"]:
            ytlink = result["link"]
            title = result["title"]
            vidid = result["id"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return {
            "title": title,
            "link": ytlink,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }

    async def track(self, link: str):
        kind, entity_id, _radio, entity = await self._entity(link)
        info = entity.get("title") or entity.get("name") or ""
        for artist in entity.get("artists") or []:
            name = artist.get("name")
            if name and "Various Artists" not in name:
                info += f" {name}"
        if not info:
            raise ValueError("Track metadata unavailable")
        details = await self._youtube_details(info)
        thumb = self._cover(entity)
        if thumb:
            details["thumb"] = thumb
        return details, entity_id

    def _queries(self, entity: dict, radio: bool = False):
        results = []
        for item in entity.get("trackList") or []:
            if item.get("isPlayable") is False:
                continue
            title = item.get("title") or ""
            subtitle = (item.get("subtitle") or "").replace("\u00a0", " ")
            name = f"{title} {subtitle}".strip()
            if name:
                results.append(name)
        if radio:
            results.append(entity.get("title") or entity.get("name") or "")
            random.shuffle(results)
        return [query for query in results if query]

    async def playlist(self, url: str):
        _kind, playlist_id, radio, entity = await self._entity(url)
        return self._queries(entity, radio), playlist_id

    async def album(self, url: str):
        _kind, album_id, _radio, entity = await self._entity(url)
        return self._queries(entity), album_id

    async def artist(self, url: str):
        _kind, artist_id, _radio, entity = await self._entity(url)
        return self._queries(entity), artist_id

    async def radio(self, url: str):
        _kind, entity_id, _radio, entity = await self._entity(url)
        return self._queries(entity, radio=True), entity_id

