
# All rights reserved.
#
import asyncio
import os
import re
import shlex
import shutil
import time

import httpx

from async_lru import alru_cache
from py_yt import VideosSearch
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from yt_dlp import YoutubeDL

from VenomX.utils.decorators import asyncify
from VenomX.utils.formatters import seconds_to_min, time_to_seconds
from VenomX.utils.notify import notify_owner

_LOG_TAG = "Youtube"
_YT_SEARCH_TIMEOUT = 10
_YT_DLP_TIMEOUT = 60
_YT_SUBPROCESS_TIMEOUT = 60
_YT_STREAM_CHECK_TIMEOUT = 8


def _log(level, msg, *a, **kw):
    import logging
    logger = logging.getLogger("VenomX.platforms.Youtube")
    getattr(logger, level)(f"[{_LOG_TAG}] {msg}", *a, **kw)


def yt_dlp_binary():
    """Locate the yt-dlp binary even if it's outside the process PATH."""
    path = shutil.which("yt-dlp")
    if path:
        return path
    for candidate in (
        os.path.expanduser("~/.local/bin/yt-dlp"),
        os.path.expanduser("~/bin/yt-dlp"),
        "/usr/local/bin/yt-dlp",
        "/usr/bin/yt-dlp",
        "/usr/sbin/yt-dlp",
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return "yt-dlp"


def cookies():
    folder_path = f"{os.getcwd()}/cookies"
    if not os.path.isdir(folder_path):
        _log("warning", "cookies folder not found at %s", folder_path)
        return None
    txt_files = [file for file in os.listdir(folder_path) if file.endswith(".txt")]
    if not txt_files:
        _log("warning", "no .txt files in cookies folder")
        return None
    for cookie_txt_file in txt_files:
        cookie_txt_file = os.path.join(folder_path, cookie_txt_file)
        try:
            with open(cookie_txt_file) as f:
                header = f.read(200)
        except Exception as e:
            _log("warning", "failed to read cookie file %s: %s", cookie_txt_file, e)
            continue
        if "# Netscape HTTP Cookie File" in header or "# HTTP Cookie File" in header:
            _log("info", "using cookie file: %s", cookie_txt_file)
            return cookie_txt_file
    _log("warning", "no valid Netscape cookie file found")
    return None


NOTHING = {"cookies_dead": None}


async def shell_cmd(cmd):
    _log("debug", "shell_cmd: %s", cmd[:200])
    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, errorz = await asyncio.wait_for(
            proc.communicate(), timeout=_YT_SUBPROCESS_TIMEOUT
        )
        elapsed = time.monotonic() - t0
        _log("debug", "shell_cmd completed in %.1fs", elapsed)
        if errorz:
            if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
                return out.decode("utf-8")
            else:
                return errorz.decode("utf-8")
        return out.decode("utf-8")
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        _log("error", "shell_cmd TIMEOUT after %.1fs: %s", elapsed, cmd[:100])
        try:
            proc.kill()
        except Exception:
            pass
        try:
            import asyncio as _aio
            _aio.get_event_loop().create_task(
                notify_owner("Youtube.shell_cmd", Exception(f"shell subprocess timed out after {elapsed:.0f}s"), f"cmd={cmd[:120]}")
            )
        except Exception:
            pass
        return ""
    except Exception as e:
        _log("error", "shell_cmd failed: %s", e)
        return ""


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: bool | str = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    @property
    def use_fallback(self):
        return NOTHING["cookies_dead"] is True

    @use_fallback.setter
    def use_fallback(self, value):
        if NOTHING["cookies_dead"] is None:
            NOTHING["cookies_dead"] = value

    @asyncify
    def url(self, message_1: Message) -> str | None:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    @alru_cache(maxsize=256)
    async def details(self, link: str, videoid: bool | str = None):
        _log("info", "details() link=%s videoid=%s", link[:80], videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1, timeout=_YT_SEARCH_TIMEOUT)
            search_result = await asyncio.wait_for(
                results.next(), timeout=_YT_SEARCH_TIMEOUT + 5
            )
            items = search_result.get("result", [])
            if not items:
                _log("warning", "details() empty results for: %s", link[:80])
                raise Exception("no search results")
            result = items[0]
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
            _log(
                "info",
                "details() OK in %.1fs title=%s vidid=%s",
                time.monotonic() - t0,
                title[:40],
                vidid,
            )
            return title, duration_min, duration_sec, thumbnail, vidid
        except asyncio.TimeoutError:
            _log(
                "error",
                "details() TIMEOUT after %.1fs for: %s",
                time.monotonic() - t0,
                link[:80],
            )
            raise
        except Exception as e:
            _log(
                "error",
                "details() FAILED after %.1fs for: %s err=%s",
                time.monotonic() - t0,
                link[:80],
                e,
            )
            raise

    @alru_cache(maxsize=256)
    async def title(self, link: str, videoid: bool | str = None):
        _log("info", "title() link=%s videoid=%s", link[:80], videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1, timeout=_YT_SEARCH_TIMEOUT)
            search_result = await asyncio.wait_for(
                results.next(), timeout=_YT_SEARCH_TIMEOUT + 5
            )
            items = search_result.get("result", [])
            if not items:
                raise Exception("no search results")
            title = items[0]["title"]
            _log("info", "title() OK in %.1fs: %s", time.monotonic() - t0, title[:50])
            return title
        except asyncio.TimeoutError:
            _log("error", "title() TIMEOUT after %.1fs for: %s", time.monotonic() - t0, link[:80])
            raise
        except Exception as e:
            _log("error", "title() FAILED for: %s err=%s", link[:80], e)
            raise

    @alru_cache(maxsize=256)
    async def duration(self, link: str, videoid: bool | str = None):
        _log("info", "duration() link=%s videoid=%s", link[:80], videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1, timeout=_YT_SEARCH_TIMEOUT)
            search_result = await asyncio.wait_for(
                results.next(), timeout=_YT_SEARCH_TIMEOUT + 5
            )
            items = search_result.get("result", [])
            if not items:
                raise Exception("no search results")
            duration = items[0]["duration"]
            _log("info", "duration() OK in %.1fs: %s", time.monotonic() - t0, duration)
            return duration
        except asyncio.TimeoutError:
            _log("error", "duration() TIMEOUT for: %s", link[:80])
            raise
        except Exception as e:
            _log("error", "duration() FAILED for: %s err=%s", link[:80], e)
            raise

    @alru_cache(maxsize=256)
    async def thumbnail(self, link: str, videoid: bool | str = None):
        _log("info", "thumbnail() link=%s videoid=%s", link[:80], videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1, timeout=_YT_SEARCH_TIMEOUT)
            search_result = await asyncio.wait_for(
                results.next(), timeout=_YT_SEARCH_TIMEOUT + 5
            )
            items = search_result.get("result", [])
            if not items:
                raise Exception("no search results")
            thumbnail = items[0]["thumbnails"][0]["url"].split("?")[0]
            _log("info", "thumbnail() OK in %.1fs", time.monotonic() - t0)
            return thumbnail
        except asyncio.TimeoutError:
            _log("error", "thumbnail() TIMEOUT for: %s", link[:80])
            raise
        except Exception as e:
            _log("error", "thumbnail() FAILED for: %s err=%s", link[:80], e)
            raise

    async def video(self, link: str, videoid: bool | str = None):
        _log("info", "video() link=%s videoid=%s", link[:80], videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cmd = [
            yt_dlp_binary(),
            "-g",
            "-f",
            "bestvideo[height<=?720][ext=mp4]+bestaudio[ext=m4a]/best[height<=?720]",
            f"{link}",
        ]
        cookie_txt_file = cookies()
        if cookie_txt_file:
            cmd[1:1] = ["--cookies", cookie_txt_file]
        _log("info", "video() subprocess: %s", " ".join(cmd[:6]))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_YT_SUBPROCESS_TIMEOUT
            )
            elapsed = time.monotonic() - t0
            if stdout:
                url = stdout.decode().split("\n")[0]
                _log("info", "video() OK in %.1fs url_len=%d", elapsed, len(url))
                return 1, url
            else:
                err = stderr.decode()[:200]
                _log("error", "video() FAILED in %.1fs stderr=%s", elapsed, err)
                return 0, err
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            _log("error", "video() TIMEOUT after %.1fs for: %s", elapsed, link[:80])
            try:
                proc.kill()
            except Exception:
                pass
            try:
                import asyncio as _aio
                _aio.get_event_loop().create_task(
                    notify_owner("Youtube.video", Exception(f"yt-dlp subprocess timed out after {elapsed:.0f}s"), f"link={link[:80]}")
                )
            except Exception:
                pass
            return 0, "timeout"
        except Exception as e:
            _log("error", "video() EXCEPTION: %s", e)
            return 0, str(e)

    async def _streamable(self, url: str) -> bool:
        """True if the direct URL can be pulled by a plain HTTP client."""
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=_YT_STREAM_CHECK_TIMEOUT
            ) as client:
                resp = await client.get(url, headers={"Range": "bytes=0-1023"})
            return resp.status_code in (200, 206)
        except Exception:
            return False

    async def stream_url(
        self,
        link: str,
        videoid: bool | str = None,
        video: bool = False,
    ):
        _log("info", "stream_url() link=%s videoid=%s video=%s", link[:80], videoid, video)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if video:
            fmt = "bestvideo[height<=?720][acodec!=none]/best[height<=?720]"
        else:
            fmt = "bestaudio[ext=m4a]/bestaudio"
        cmd = [
            yt_dlp_binary(),
            "-g",
            "-f",
            fmt,
            f"{link}",
        ]
        cookie_txt_file = cookies()
        if cookie_txt_file:
            cmd[1:1] = ["--cookies", cookie_txt_file]
        _log("info", "stream_url() subprocess: %s", " ".join(cmd[:8]))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_YT_SUBPROCESS_TIMEOUT
            )
            elapsed = time.monotonic() - t0
            if stdout:
                url = stdout.decode().split("\n")[0]
                _log("info", "stream_url() got url in %.1fs, checking streamable...", elapsed)
                if await self._streamable(url):
                    _log("info", "stream_url() streamable OK in %.1fs total", time.monotonic() - t0)
                    return 1, url
                _log("warning", "stream_url() NOT streamable in %.1fs", time.monotonic() - t0)
                return 0, stderr.decode() or (
                    "Direct stream is not available right now, downloading instead."
                )
            else:
                err = stderr.decode()[:200]
                _log("error", "stream_url() FAILED in %.1fs stderr=%s", elapsed, err)
                return 0, err
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            _log("error", "stream_url() TIMEOUT after %.1fs for: %s", elapsed, link[:80])
            try:
                proc.kill()
            except Exception:
                pass
            try:
                import asyncio as _aio
                _aio.get_event_loop().create_task(
                    notify_owner("Youtube.stream_url", Exception(f"yt-dlp subprocess timed out after {elapsed:.0f}s"), f"link={link[:80]} video={video}")
                )
            except Exception:
                pass
            return 0, "timeout"
        except Exception as e:
            _log("error", "stream_url() EXCEPTION: %s", e)
            return 0, str(e)

    @alru_cache(maxsize=256)
    async def playlist(self, link, limit, videoid: bool | str = None):
        _log("info", "playlist() link=%s limit=%s videoid=%s", link[:80], limit, videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]

        cmd = (
            f"{shlex.quote(yt_dlp_binary())} -i --compat-options no-youtube-unavailable-videos "
            f'--get-id --flat-playlist --playlist-end {limit} --skip-download "{link}" '
            f"2>/dev/null"
        )

        playlist = await shell_cmd(cmd)

        try:
            result = [key for key in playlist.split("\n") if key]
        except Exception:
            result = []
        _log("info", "playlist() OK in %.1fs got %d items", time.monotonic() - t0, len(result))
        return result

    @alru_cache(maxsize=256)
    async def track(self, link: str, videoid: bool | str = None):
        _log("info", "track() link=%s videoid=%s", link[:80], videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if link.startswith("http://") or link.startswith("https://"):
            _log("info", "track() URL detected, delegating to _track()")
            return await self._track(link)
        try:
            _log("info", "track() search query, trying VideosSearch...")
            results = VideosSearch(link, limit=1, timeout=_YT_SEARCH_TIMEOUT)
            search_result = await asyncio.wait_for(
                results.next(), timeout=_YT_SEARCH_TIMEOUT + 5
            )
            items = search_result.get("result", [])
            if not items:
                _log("warning", "track() VideosSearch empty, falling back to _track()")
                return await self._track(link)
            result = items[0]
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            track_details = {
                "title": title,
                "link": yturl,
                "vidid": vidid,
                "duration_min": duration_min,
                "thumb": thumbnail,
            }
            _log(
                "info",
                "track() OK via VideosSearch in %.1fs title=%s vidid=%s",
                time.monotonic() - t0,
                title[:40],
                vidid,
            )
            return track_details, vidid
        except asyncio.TimeoutError:
            _log(
                "error",
                "track() VideosSearch TIMEOUT after %.1fs, falling back to _track()",
                time.monotonic() - t0,
            )
            try:
                return await self._track(link)
            except Exception as e2:
                _log("error", "track() _track() ALSO FAILED: %s", e2)
                try:
                    await notify_owner("Youtube.track", e2, f"query={link[:80]} (VideosSearch timed out, _track also failed)")
                except Exception:
                    pass
                raise
        except Exception as e:
            _log(
                "warning",
                "track() VideosSearch FAILED: %s, falling back to _track()",
                e,
            )
            try:
                return await self._track(link)
            except Exception as e2:
                _log("error", "track() _track() ALSO FAILED: %s", e2)
                try:
                    await notify_owner("Youtube.track", e2, f"query={link[:80]} (VideosSearch error: {e}, _track also failed)")
                except Exception:
                    pass
                raise

    @asyncify
    def _track(self, q):
        _log("info", "_track() ytsearch: %s", q[:80])
        t0 = time.monotonic()
        options = {
            "format": "bestaudio[ext=m4a]/bestaudio",
            "noplaylist": True,
            "quiet": True,
            "extract_flat": "in_playlist",
            "cookiefile": cookies(),
        }
        try:
            with YoutubeDL(options) as ydl:
                info_dict = ydl.extract_info(f"ytsearch: {q}", download=False)
                elapsed = time.monotonic() - t0
                if not info_dict or not info_dict.get("entries"):
                    _log("error", "_track() no entries in %.1fs for: %s", elapsed, q[:80])
                    raise Exception("no entries from ytsearch")
                details = info_dict["entries"][0]
                info = {
                    "title": details["title"],
                    "link": details["url"],
                    "vidid": details["id"],
                    "duration_min": (
                        seconds_to_min(details["duration"])
                        if details["duration"] != 0
                        else None
                    ),
                    "thumb": details["thumbnails"][0]["url"],
                }
                _log(
                    "info",
                    "_track() OK in %.1fs title=%s vidid=%s",
                    elapsed,
                    info["title"][:40],
                    info["vidid"],
                )
                return info, details["id"]
        except Exception as e:
            elapsed = time.monotonic() - t0
            _log("error", "_track() FAILED after %.1fs for: %s err=%s", elapsed, q[:80], e)
            try:
                import asyncio as _aio
                _aio.get_event_loop().create_task(
                    notify_owner("Youtube._track(yt-dlp)", e, f"query={q[:80]} elapsed={elapsed:.1f}s")
                )
            except Exception:
                pass
            raise

    @alru_cache(maxsize=256)
    @asyncify
    def formats(self, link: str, videoid: bool | str = None):
        _log("info", "formats() link=%s videoid=%s", link[:80], videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        ytdl_opts = {
            "quiet": True,
            "cookiefile": cookies(),
        }

        ydl = YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except Exception:
                    continue
                if "dash" not in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except KeyError:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        _log("info", "formats() OK in %.1fs got %d formats", time.monotonic() - t0, len(formats_available))
        return formats_available, link

    @alru_cache(maxsize=256)
    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: bool | str = None,
    ):
        _log("info", "slider() link=%s query_type=%s videoid=%s", link[:80], query_type, videoid)
        t0 = time.monotonic()
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            a = VideosSearch(link, limit=10, timeout=_YT_SEARCH_TIMEOUT)
            search_result = await asyncio.wait_for(
                a.next(), timeout=_YT_SEARCH_TIMEOUT + 5
            )
            result = search_result.get("result")
            if not result or len(result) <= query_type:
                raise Exception("insufficient search results for slider")
            title = result[query_type]["title"]
            duration_min = result[query_type]["duration"]
            vidid = result[query_type]["id"]
            thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
            _log("info", "slider() OK in %.1fs title=%s", time.monotonic() - t0, title[:40])
            return title, duration_min, thumbnail, vidid
        except asyncio.TimeoutError:
            _log("error", "slider() TIMEOUT after %.1fs", time.monotonic() - t0)
            raise
        except Exception as e:
            _log("error", "slider() FAILED: %s", e)
            raise

    async def download(
        self,
        link: str,
        mystic,
        video: bool | str = None,
        videoid: bool | str = None,
        songaudio: bool | str = None,
        songvideo: bool | str = None,
        format_id: bool | str = None,
        title: bool | str = None,
    ) -> str:
        _log(
            "info",
            "download() link=%s videoid=%s video=%s songaudio=%s songvideo=%s format_id=%s",
            link[:80],
            videoid,
            video,
            songaudio,
            songvideo,
            format_id,
        )
        t0 = time.monotonic()
        if videoid:
            link = self.base + link

        @asyncify
        def audio_dl():
            dl_t0 = time.monotonic()
            _log("info", "audio_dl() starting for: %s", link[:80])
            ydl_optssx = {
                "format": "bestaudio[ext=m4a]/bestaudio",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "noplaylist": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookies(),
                "prefer_ffmpeg": True,
                "no_overwrites": True,
            }

            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, False)
                _log("info", "audio_dl() extract_info done in %.1fs", time.monotonic() - dl_t0)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    fsize = os.path.getsize(xyz)
                    if fsize < 10240:
                        _log("warning", "audio_dl() stale/incomplete file (%d bytes), re-downloading: %s", fsize, xyz)
                        try:
                            os.remove(xyz)
                        except Exception:
                            pass
                    else:
                        _log("info", "audio_dl() file exists (%d bytes): %s", fsize, xyz)
                        return xyz
                x.download([link])
                final_size = os.path.getsize(xyz) if os.path.exists(xyz) else 0
                _log("info", "audio_dl() download done in %.1fs size=%d -> %s", time.monotonic() - dl_t0, final_size, xyz)
                return xyz

        @asyncify
        def video_dl():
            dl_t0 = time.monotonic()
            _log("info", "video_dl() starting for: %s", link[:80])
            ydl_optssx = {
                "format": "best[height<=480][ext=mp4]/best[height<=480]/bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "noplaylist": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "cookiefile": cookies(),
                "no_overwrites": True,
                "merge_output_format": "mp4",
            }

            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, False)
                _log("info", "video_dl() extract_info done in %.1fs", time.monotonic() - dl_t0)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    fsize = os.path.getsize(xyz)
                    if fsize < 10240:
                        _log("warning", "video_dl() stale/incomplete file (%d bytes), re-downloading: %s", fsize, xyz)
                        try:
                            os.remove(xyz)
                        except Exception:
                            pass
                    else:
                        _log("info", "video_dl() file exists (%d bytes): %s", fsize, xyz)
                        return xyz
                x.download([link])
                final_size = os.path.getsize(xyz) if os.path.exists(xyz) else 0
                _log("info", "video_dl() download done in %.1fs size=%d -> %s", time.monotonic() - dl_t0, final_size, xyz)
                return xyz
                x.download([link])
                _log("info", "video_dl() download done in %.1fs -> %s", time.monotonic() - dl_t0, xyz)
                return xyz

        @asyncify
        def song_video_dl():
            dl_t0 = time.monotonic()
            formats = f"{format_id}+bestaudio[ext=m4a]/bestaudio"
            _log("info", "song_video_dl() starting format=%s for: %s", formats, link[:80])
            ydl_optssx = {
                "format": formats,
                "outtmpl": os.path.join("downloads", f"%(id)s_{format_id}.%(ext)s"),
                "geo_bypass": True,
                "noplaylist": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
                "cookiefile": cookies(),
                "no_overwrites": True,
            }

            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link)
                _log("info", "song_video_dl() done in %.1fs", time.monotonic() - dl_t0)
                filename = f"{info['id']}_{format_id}.mp4"
                file_path = os.path.join("downloads", filename)
                return file_path

        @asyncify
        def song_audio_dl():
            dl_t0 = time.monotonic()
            _log("info", "song_audio_dl() starting format=%s for: %s", format_id, link[:80])
            ydl_optssx = {
                "format": format_id,
                "outtmpl": os.path.join("downloads", f"%(id)s_{format_id}.%(ext)s"),
                "geo_bypass": True,
                "noplaylist": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "cookiefile": cookies(),
                "no_overwrites": True,
            }

            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link)
                _log("info", "song_audio_dl() done in %.1fs", time.monotonic() - dl_t0)
                filename = f"{info['id']}_{format_id}.mp3"
                file_path = os.path.join("downloads", filename)
                return file_path

        try:
            if songvideo:
                _log("info", "download() dispatching song_video_dl()")
                result = await asyncio.wait_for(
                    song_video_dl(), timeout=_YT_DLP_TIMEOUT * 3
                )
            elif songaudio:
                _log("info", "download() dispatching song_audio_dl()")
                result = await asyncio.wait_for(
                    song_audio_dl(), timeout=_YT_DLP_TIMEOUT * 3
                )
            elif video:
                _log("info", "download() dispatching video_dl()")
                direct = True
                result = await asyncio.wait_for(
                    video_dl(), timeout=_YT_DLP_TIMEOUT * 3
                )
            else:
                _log("info", "download() dispatching audio_dl()")
                direct = True
                result = await asyncio.wait_for(
                    audio_dl(), timeout=_YT_DLP_TIMEOUT * 3
                )

            elapsed = time.monotonic() - t0
            _log("info", "download() COMPLETED in %.1fs result=%s", elapsed, str(result)[:100])
            return result, True
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            _log("error", "download() TIMEOUT after %.1fs", elapsed)
            try:
                import asyncio as _aio
                _aio.get_event_loop().create_task(
                    notify_owner("Youtube.download", Exception(f"yt-dlp download timed out after {elapsed:.0f}s"), f"link={link[:80]} video={video} songaudio={songaudio} songvideo={songvideo}")
                )
            except Exception:
                pass
            raise Exception(f"download timed out after {elapsed:.0f}s")
        except Exception as e:
            elapsed = time.monotonic() - t0
            _log("error", "download() FAILED after %.1fs err=%s", elapsed, e)
            try:
                import asyncio as _aio
                _aio.get_event_loop().create_task(
                    notify_owner("Youtube.download", e, f"link={link[:80]} elapsed={elapsed:.1f}s video={video}")
                )
            except Exception:
                pass
            raise
