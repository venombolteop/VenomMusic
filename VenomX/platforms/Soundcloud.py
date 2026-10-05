
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
            "quiet": True,
            "no_warnings": True,
            "progress": False,
        }
        self.flat_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }

    async def valid(self, link: str) -> bool:
        return "soundcloud" in link

    @asyncify
    def download(self, url: str) -> dict | bool:
        target = url
        with YoutubeDL(self.flat_opts) as ydl:
            try:
                probe = ydl.extract_info(url, download=False)
            except Exception:
                probe = None
            if probe and probe.get("entries"):
                entry = next((item for item in probe["entries"] if item), None)
                if not entry:
                    return False
                target = entry.get("url") or entry.get("webpage_url") or url
                if target == url:
                    return False

        with YoutubeDL(self.opts) as ydl:
            try:
                info = ydl.extract_info(target)
            except Exception:
                return False
            if not info or "ext" not in info:
                return False
            duration_sec = info.get("duration") or 0
            xyz = path.join(
                "downloads", f"{info['id']}.{info.get('ext', 'm4a')}"
            )
            track_details = {
                "title": info.get("title") or info.get("id"),
                "duration_sec": duration_sec,
                "duration_min": seconds_to_min(duration_sec),
                "uploader": info.get("uploader") or info.get("channel") or "",
                "filepath": xyz,
            }
            return track_details, xyz
