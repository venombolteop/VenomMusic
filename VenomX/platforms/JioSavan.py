# All rights reserved.
#

import os

import aiohttp
import requests
import yt_dlp

from io import BytesIO
from PIL import Image

from config import seconds_to_time
from VenomX.utils.decorators import asyncify

API = "https://www.jiosaavn.com/api.php"
WEB_CALL = {
    "__call": "webapi.get",
    "_format": "json",
    "_marker": "0",
    "ctx": "web6dot0",
}
SEARCH_CALL = {
    "__call": "autocomplete.get",
    "_format": "json",
    "_marker": "0",
    "ctx": "web6dot0",
    "type": "song",
    "limit": 5,
}


class Saavn:

    @staticmethod
    async def valid(url: str) -> bool:
        return "jiosaavn.com" in url or "saavn.com" in url

    @staticmethod
    async def is_song(url: str) -> bool:
        return "song" in url and not "/featured/" in url and "/album/" not in url

    @staticmethod
    async def is_playlist(url: str) -> bool:
        return "/featured/" in url or "/album" in url

    def clean_url(self, url: str) -> str:
        if "#" in url:
            url = url.split("#")[0]
        return url

    def token(self, url: str) -> str:
        return self.clean_url(url).rstrip("/").split("/")[-1]

    @asyncify
    def playlist(self, url, limit):
        clean_url = self.clean_url(url)
        ydl_opts = {
            "extract_flat": True,
            "force_generic_extractor": True,
            "quiet": True,
            "no_warnings": True,
        }
        song_info = []
        count = 0
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                playlist_info = ydl.extract_info(clean_url, download=False)
                for entry in playlist_info["entries"]:
                    if count == limit:
                        break
                    duration_sec = entry.get("duration", 0)
                    info = {
                        "title": entry["title"],
                        "duration_sec": duration_sec,
                        "duration_min": seconds_to_time(duration_sec),
                        "thumb": entry.get("thumbnail", ""),
                        "url": self.clean_url(entry["webpage_url"]),
                    }
                    song_info.append(info)
                    count += 1
            except Exception:
                pass
        return song_info

    @asyncify
    def _song(self, token: str) -> dict:
        params = dict(WEB_CALL, token=token, type="song")
        response = requests.get(API, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        return self._pick_song(data, token)

    @staticmethod
    def _pick_song(data, token: str) -> dict:
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            songs = data.get("songs")
            if isinstance(songs, list) and songs:
                return songs[0]
            if isinstance(songs, dict) and songs:
                return list(songs.values())[0]
            if token in data and isinstance(data[token], dict):
                return data[token]
            for value in data.values():
                if isinstance(value, dict) and value.get("song"):
                    return value
        raise ValueError("Song not found")

    async def _search(self, query: str) -> dict:
        params = dict(SEARCH_CALL, query=query)
        response = requests.get(API, params=params, timeout=20)
        response.raise_for_status()
        songs = (response.json().get("songs") or {}).get("data") or []
        if not songs:
            raise ValueError("No results found")
        match = songs[0]
        token = self.token(match.get("url") or "") or match.get("id")
        if token:
            try:
                song = await self._song(token)
                song.setdefault("perma_url", match.get("url"))
                return song
            except Exception:
                return match
        return match

    @asyncify
    def _media_url(self, encrypted: str, bitrate: str = "128") -> str:
        response = requests.post(
            f"{API}?__call=song.generateAuthToken&_format=json&bitrate={bitrate}",
            data={"url": encrypted},
            timeout=20,
        )
        response.raise_for_status()
        auth_url = response.json().get("auth_url")
        if not auth_url:
            raise ValueError("Could not resolve media url")
        return auth_url

    async def info(self, url):
        url = self.clean_url(url)
        if "jiosaavn.com" in url or "saavn.com" in url:
            info = await self._song(self.token(url))
        else:
            info = await self._search(url)

        image = info.get("image")
        if isinstance(image, list):
            image = image[-1].get("url") if isinstance(image[-1], dict) else image[-1]
        elif isinstance(image, dict):
            image = image.get("url")

        more_info = info.get("more_info")
        more_info = more_info if isinstance(more_info, dict) else {}
        song_id = info.get("id") or self.token(url)
        thumb_path = await self._resize_thumb(image, song_id) if image else ""
        encrypted = more_info.get("encrypted_media_url") or info.get("encrypted_media_url") or ""

        return {
            "title": info.get("name") or info.get("song") or info.get("title"),
            "duration_sec": int(info.get("duration") or 0),
            "duration_min": seconds_to_time(int(info.get("duration") or 0)),
            "thumb": thumb_path,
            "url": more_info.get("perma_url") or info.get("perma_url") or info.get("url") or url,
            "_download_url": await self._media_url(encrypted) if encrypted else "",
            "_id": song_id,
        }

    async def download(self, url):
        details = await self.info(url)
        file_path = os.path.join("downloads", f"Saavn_{details['_id']}.mp3")

        if not os.path.exists(file_path):
            async with aiohttp.ClientSession() as session:
                async with session.get(details["_download_url"]) as resp:
                    if resp.status == 200:
                        with open(file_path, "wb") as f:
                            while chunk := await resp.content.read(1024):
                                f.write(chunk)
                        print(f"Downloaded: {file_path}")
                    else:
                        raise ValueError(
                            f"Failed to download {details['_download_url']}. HTTP Status: {resp.status}"
                        )

        details["filepath"] = file_path
        return file_path, details

    async def _resize_thumb(self, thumb_url, _id, size=(1280, 720)):
        thumb_path = os.path.join("cache", f"Thumb_{_id}.jpg")

        if os.path.exists(thumb_path):
            return thumb_path

        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as response:
                img_data = await response.read()

        img = Image.open(BytesIO(img_data))
        scale_factor = size[1] / img.height
        new_width = int(img.width * scale_factor)
        new_height = size[1]

        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        new_img = Image.new("RGB", size, (0, 0, 0))
        new_img.paste(resized_img, ((size[0] - new_width) // 2, 0))

        new_img.save(thumb_path, format="JPEG")
        return thumb_path

