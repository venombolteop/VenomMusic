
# All rights reserved.
#

from os import path

from yt_dlp import YoutubeDL

from VenomX.utils.decorators import asyncify
from VenomX.utils.formatters import seconds_to_min


class SoundCloud:
    def __init__(self):
        self.opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "format": "best",
            "retries": 3,
            "nooverwrites": False,
            "continuedl": True,
        }

    async def valid(self, link: str) -> bool:
        return "soundcloud" in link

    @asyncify
    def download(self, url: str) -> dict | bool:
        with YoutubeDL(self.opts):
            try:
                info = d.extract_info(url)
            except Exception:
                return False
            xyz = path.join("downloads", f"{info['id']}.{info['ext']}")
            duration_min = seconds_to_min(info["duration"])
            track_details = {
                "title": info["title"],
                "duration_sec": info["duration"],
                "duration_min": duration_min,
                "uploader": info["uploader"],
                "filepath": xyz,
            }
            return track_details, xyz
