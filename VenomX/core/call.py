
# All rights reserved.
#
import asyncio
from typing import Union

from ntgcalls import TelegramServerError
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, filters
try:
    from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall
except ImportError:
    from pytgcalls.exceptions import NoActiveGroupCall

    AlreadyJoinedError = NoActiveGroupCall
from pytgcalls.types import (
    ChatUpdate,
    GroupCallConfig,
    MediaStream,
    Update,
)
from pytgcalls.types import StreamEnded

import config
from strings import get_string
from VenomX import LOGGER, Platform, app, userbot
from VenomX.misc import db
from VenomX.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_audio_bitrate,
    get_instant_play,
    get_lang,
    get_loop,
    get_video_bitrate,
    group_assistant,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from VenomX.utils.exceptions import AssistantErr
from VenomX.utils.inline.play import stream_markup, telegram_markup
from VenomX.utils.stream.autoclear import auto_clean
from VenomX.utils.thumbnails import gen_thumb

from pyrogram.errors import (
    ChannelsTooMuch,
    ChatAdminRequired,
    FloodWait,
    InviteRequestSent,
    UserAlreadyParticipant,
)

from VenomX.core.userbot import assistants
from VenomX.utils.database import (
    get_assistant,
    get_lang,
    set_assistant,
)

links = {}

# YouTube direct URLs are IP-bound to the proxy that fetched them.
# FFmpeg must use the same proxy or playback is silent (HTTP 403).
_PROXY = (getattr(config, "PROXY_URL", None) or "").strip()
_PROXY_FFMPEG = f"-http_proxy {_PROXY} " if _PROXY else ""

# ffmpeg parameters for remote URLs (YouTube direct streams via proxy).
# -reconnect flags BREAK through HTTP proxies — removed.
# Increased thread_queue_size to prevent audio pipeline starvation in group calls.
_REMOTE_FFMPEG_PARAMS = (
    f"{_PROXY_FFMPEG}"
    "-analyzeduration 5000000 -probesize 131072 "
    "-thread_queue_size 4096 "
    "-fflags +genpts+discardcorrupt "
    "-flags low_delay"
)

# For local files: buffer tuning to prevent pipe starvation
_LOCAL_FFMPEG_PARAMS = (
    "-thread_queue_size 4096 "
    "-analyzeduration 5000000 -probesize 131072 "
    "-fflags +genpts+discardcorrupt "
    "-flags low_delay"
)

# Video-specific: faster decode + lower buffer for real-time pipe streaming
_REMOTE_FFMPEG_PARAMS_VIDEO = (
    f"{_PROXY_FFMPEG}"
    "-analyzeduration 3000000 -probesize 65536 "
    "-thread_queue_size 2048 "
    "-fflags +genpts+discardcorrupt+nobuffer "
    "-flags low_delay"
)

_LOCAL_FFMPEG_PARAMS_VIDEO = (
    "-thread_queue_size 2048 "
    "-analyzeduration 3000000 -probesize 65536 "
    "-fflags +genpts+discardcorrupt+nobuffer "
    "-flags low_delay"
)


async def _clear_(chat_id):
    popped = db.pop(chat_id, None)
    if popped:
        await auto_clean(popped)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)


class Call:
    def __init__(self):
        self.calls = []

        for client in userbot.clients:
            pycall = PyTgCalls(
                client,
                cache_duration=100,
            )
            self.calls.append(pycall)

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause_stream(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume_stream(chat_id)

    async def mute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.mute_stream(chat_id)

    async def unmute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute_stream(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_call(chat_id)
        except Exception as e:
            LOGGER(__name__).error(f"Failed to stop stream for chat {chat_id}: {e}")

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            check.pop(0)
        except Exception as e:
            LOGGER(__name__).error(f"Error popping queue for chat {chat_id}: {e}")
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_call(chat_id, close=False)
        except Exception as e:
            LOGGER(__name__).error(f"Failed to force leave call for chat {chat_id}: {e}")

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = await get_video_bitrate(chat_id)
        call_config = GroupCallConfig(auto_start=False)
        is_remote = isinstance(link, str) and link.startswith("http")
        if video:
            ffmpeg_params = _REMOTE_FFMPEG_PARAMS_VIDEO if is_remote else _LOCAL_FFMPEG_PARAMS_VIDEO
        else:
            ffmpeg_params = _REMOTE_FFMPEG_PARAMS if is_remote else _LOCAL_FFMPEG_PARAMS
        if video:
            stream = MediaStream(
                link,
                audio_parameters=audio_stream_quality,
                video_parameters=video_stream_quality,
                ffmpeg_parameters=ffmpeg_params,
            )
        elif image and config.PRIVATE_BOT_MODE == str(True):
            stream = MediaStream(
                image,
                audio_path=link,
                audio_parameters=audio_stream_quality,
                video_parameters=video_stream_quality,
                ffmpeg_parameters=ffmpeg_params,
            )
        else:
            stream = MediaStream(
                link,
                audio_parameters=audio_stream_quality,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=ffmpeg_params,
            )

        await assistant.play(chat_id, stream, config=call_config)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = await get_video_bitrate(chat_id)
        call_config = GroupCallConfig(auto_start=False)
        is_remote = isinstance(file_path, str) and file_path.startswith("http")
        proxy_part = _PROXY_FFMPEG if is_remote else ""
        stream = (
            MediaStream(
                file_path,
                audio_parameters=audio_stream_quality,
                video_parameters=video_stream_quality,
                ffmpeg_parameters=f"{proxy_part}-ss {to_seek} -to {duration} -thread_queue_size 2048 -analyzeduration 3000000 -probesize 65536 -fflags +genpts+discardcorrupt+nobuffer -flags low_delay",
            )
            if mode == "video"
            else MediaStream(
                file_path,
                audio_parameters=audio_stream_quality,
                ffmpeg_parameters=f"{proxy_part}-ss {to_seek} -to {duration} -thread_queue_size 4096 -analyzeduration 5000000 -probesize 131072 -fflags +genpts+discardcorrupt -flags low_delay",
                video_flags=MediaStream.Flags.IGNORE,
            )
        )
        await assistant.play(chat_id, stream, config=call_config)

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        join_as = getattr(assistant, "_cache_local_peer", None)
        if join_as is None:
            try:
                join_as = await assistant._app.resolve_peer(
                    await assistant._app.get_id()
                )
            except Exception as exc:
                LOGGER(__name__).warning(
                    f"Could not resolve assistant peer for stream check: "
                    f"{type(exc).__name__}: {exc}"
                )
        call_config = GroupCallConfig(auto_start=False, join_as=join_as)
        try:
            await assistant.play(
                config.LOGGER_ID,
                MediaStream(link),
                config=call_config,
            )
            await asyncio.sleep(0.5)
            await assistant.leave_call(config.LOGGER_ID)
        except NoActiveGroupCall:
            raise
        except Exception as exc:
            LOGGER(__name__).warning(
                f"Stream sanity check failed: {type(exc).__name__}: {exc}"
            )

    async def join_chat(self, chat_id, attempts=1):
        max_attempts = len(assistants) - 1
        userbot = await get_assistant(chat_id)
        try:
            language = await get_lang(chat_id)
            _ = get_string(language)
        except Exception:
            _ = get_string("en")
        try:
            chat = await app.get_chat(chat_id)
        except ChatAdminRequired:
            raise AssistantErr(_["call_1"])
        except Exception as e:
            raise AssistantErr(_["call_3"].format(app.mention, type(e).__name__))
        if chat_id in links:
            invitelink = links[chat_id]
        else:
            if chat.username:
                invitelink = chat.username
                try:
                    await userbot.resolve_peer(invitelink)
                except Exception:
                    pass
            else:
                try:
                    invitelink = await app.export_chat_invite_link(chat_id)
                except ChatAdminRequired:
                    raise AssistantErr(_["call_1"])
                except Exception as e:
                    raise AssistantErr(
                        _["call_3"].format(app.mention, type(e).__name__)
                    )

            if invitelink.startswith("https://t.me/+"):
                invitelink = invitelink.replace(
                    "https://t.me/+", "https://t.me/joinchat/"
                )
            links[chat_id] = invitelink

        try:
            await asyncio.sleep(1)
            await userbot.join_chat(invitelink)
        except InviteRequestSent:
            try:
                await app.approve_chat_join_request(chat_id, userbot.id)
            except Exception as e:
                raise AssistantErr(_["call_3"].format(type(e).__name__))
            await asyncio.sleep(1)
            raise AssistantErr(_["call_6"].format(app.mention))
        except UserAlreadyParticipant:
            pass
        except ChannelsTooMuch:
            if attempts <= max_attempts:
                attempts += 1
                userbot = await set_assistant(chat_id)
                return await self.join_chat(chat_id, attempts)
            else:
                raise AssistantErr(_["call_9"].format(config.SUPPORT_GROUP))
        except FloodWait as e:
            time = e.value
            if time < 20:
                await asyncio.sleep(time)
                attempts += 1
                return await self.join_chat(chat_id, attempts)
            else:
                if attempts <= max_attempts:
                    attempts += 1
                    userbot = await set_assistant(chat_id)
                    return await self.join_chat(chat_id, attempts)

                raise AssistantErr(_["call_10"].format(time))
        except Exception as e:
            raise AssistantErr(_["call_3"].format(type(e).__name__))

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = await get_video_bitrate(chat_id)
        call_config = GroupCallConfig(auto_start=False)
        is_remote = isinstance(link, str) and link.startswith("http")
        if video:
            ffmpeg_params = _REMOTE_FFMPEG_PARAMS_VIDEO if is_remote else _LOCAL_FFMPEG_PARAMS_VIDEO
        else:
            ffmpeg_params = _REMOTE_FFMPEG_PARAMS if is_remote else _LOCAL_FFMPEG_PARAMS
        if video:
            stream = MediaStream(
                link,
                audio_parameters=audio_stream_quality,
                video_parameters=video_stream_quality,
                ffmpeg_parameters=ffmpeg_params,
            )
        elif image and config.PRIVATE_BOT_MODE == str(True):
            stream = MediaStream(
                image,
                audio_path=link,
                audio_parameters=audio_stream_quality,
                video_parameters=video_stream_quality,
                ffmpeg_parameters=ffmpeg_params,
            )
        else:
            stream = MediaStream(
                link,
                audio_parameters=audio_stream_quality,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=ffmpeg_params,
            )

        try:
            await assistant.play(
                chat_id=chat_id,
                stream=stream,
                config=call_config,
            )
        except Exception:
            await self.join_chat(chat_id)
            try:
                await assistant.play(
                    chat_id=chat_id,
                    stream=stream,
                    config=call_config,
                )
            except Exception as e:
                raise AssistantErr(
                    "**No Active Voice Chat Found**\n\nPlease make sure group's voice chat is enabled. If already enabled, please end it and start fresh voice chat again and if the problem continues, try /restart"
                )

        except AlreadyJoinedError:
            raise AssistantErr(
                "**ASSISTANT IS ALREADY IN VOICECHAT **\n\nMusic bot system detected that assistant is already in the voicechat, if the problem continues restart the videochat and try again."
            )
        except TelegramServerError:
            raise AssistantErr(
                "**TELEGRAM SERVER ERROR**\n\nPlease restart Your voicechat."
            )
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            if popped:
                await auto_clean(popped)
                if popped.get("mystic"):
                    try:
                        await popped.get("mystic").delete()
                    except Exception:
                        pass
            if not check:
                await _clear_(chat_id)
                try:
                    await client.leave_call(chat_id, close=False)
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to leave call for chat {chat_id}: {e}")
                return
        except Exception as e:
            LOGGER(__name__).error(f"Error in change_stream for chat {chat_id}: {e}")
            try:
                await _clear_(chat_id)
                await client.leave_call(chat_id, close=False)
            except Exception as e2:
                LOGGER(__name__).error(f"Failed to leave call after error for chat {chat_id}: {e2}")
            return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            audio_stream_quality = await get_audio_bitrate(chat_id)
            video_stream_quality = await get_video_bitrate(chat_id)
            videoid = check[0]["vidid"]
            userid = check[0].get("user_id")
            check[0]["played"] = 0
            video = True if str(streamtype) == "video" else False
            call_config = GroupCallConfig(auto_start=False)
            if "live_" in queued:
                n, link = await Platform.youtube.video(videoid, True)
                if n == 0:
                    return await app.send_message(
                        original_chat_id,
                        text=_["call_7"],
                    )
                is_remote = isinstance(link, str) and link.startswith("http")
                ffmpeg_params = (_REMOTE_FFMPEG_PARAMS_VIDEO if is_remote else _LOCAL_FFMPEG_PARAMS_VIDEO) if video else (_REMOTE_FFMPEG_PARAMS if is_remote else _LOCAL_FFMPEG_PARAMS)
                if video:
                    stream = MediaStream(
                        link,
                        audio_parameters=audio_stream_quality,
                        video_parameters=video_stream_quality,
                        ffmpeg_parameters=ffmpeg_params,
                    )
                else:
                    try:
                        image = await Platform.youtube.thumbnail(videoid, True)
                    except Exception:
                        image = None
                    if image and config.PRIVATE_BOT_MODE == str(True):
                        stream = MediaStream(
                            image,
                            audio_path=link,
                            audio_parameters=audio_stream_quality,
                            video_parameters=video_stream_quality,
                            ffmpeg_parameters=ffmpeg_params,
                        )
                    else:
                        stream = MediaStream(
                            link,
                            audio_parameters=audio_stream_quality,
                            video_flags=MediaStream.Flags.IGNORE,
                            ffmpeg_parameters=ffmpeg_params,
                        )
                try:
                    await client.play(chat_id, stream, config=call_config)
                except Exception:
                    return await app.send_message(
                        original_chat_id,
                        text=_["call_7"],
                    )
                img = await gen_thumb(videoid)
                button = telegram_markup(_, chat_id)
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        title[:27],
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            elif "vid_" in queued:
                video = True if str(streamtype) == "video" else False
                mystic = await app.send_message(original_chat_id, _["call_8"])
                n, stream_link = await Platform.youtube.stream_url(
                    videoid, videoid=True, video=video
                )
                if n == 0:
                    try:
                        stream_link, direct = await Platform.youtube.download(
                            videoid,
                            mystic,
                            videoid=True,
                            video=video,
                        )
                    except Exception:
                        return await mystic.edit_text(
                            _["call_7"], disable_web_page_preview=True
                        )
                is_remote = isinstance(stream_link, str) and stream_link.startswith("http")
                ffmpeg_params = (_REMOTE_FFMPEG_PARAMS_VIDEO if is_remote else _LOCAL_FFMPEG_PARAMS_VIDEO) if video else (_REMOTE_FFMPEG_PARAMS if is_remote else _LOCAL_FFMPEG_PARAMS)
                if video:
                    stream = MediaStream(
                        stream_link,
                        audio_parameters=audio_stream_quality,
                        video_parameters=video_stream_quality,
                        ffmpeg_parameters=ffmpeg_params,
                    )
                else:
                    try:
                        image = await Platform.youtube.thumbnail(videoid, True)
                    except Exception:
                        image = None
                    if image and config.PRIVATE_BOT_MODE == str(True):
                        stream = MediaStream(
                            image,
                            audio_path=stream_link,
                            audio_parameters=audio_stream_quality,
                            video_parameters=video_stream_quality,
                            ffmpeg_parameters=ffmpeg_params,
                        )
                    else:
                        stream = MediaStream(
                            stream_link,
                            audio_parameters=audio_stream_quality,
                            video_flags=MediaStream.Flags.IGNORE,
                            ffmpeg_parameters=ffmpeg_params,
                        )
                try:
                    await client.play(chat_id, stream, config=call_config)
                except Exception:
                    return app.send_message(
                        original_chat_id,
                        text=_["call_7"],
                    )
                img = await gen_thumb(videoid)
                button = stream_markup(_, videoid, chat_id)
                if instant or 'mystic' in locals():
                    await mystic.delete()
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        title[:27],
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            elif "index_" in queued:
                is_remote = isinstance(videoid, str) and videoid.startswith("http")
                ffmpeg_params = (_REMOTE_FFMPEG_PARAMS_VIDEO if is_remote else _LOCAL_FFMPEG_PARAMS_VIDEO) if video else (_REMOTE_FFMPEG_PARAMS if is_remote else _LOCAL_FFMPEG_PARAMS)
                stream = (
                    MediaStream(
                        videoid,
                        audio_parameters=audio_stream_quality,
                        video_parameters=video_stream_quality,
                        ffmpeg_parameters=ffmpeg_params,
                    )
                    if str(streamtype) == "video"
                    else MediaStream(
                        videoid,
                        audio_parameters=audio_stream_quality,
                        video_flags=MediaStream.Flags.IGNORE,
                        ffmpeg_parameters=ffmpeg_params,
                    )
                )
                try:
                    await client.play(chat_id, stream, config=call_config)
                except Exception:
                    return await app.send_message(
                        original_chat_id,
                        text=_["call_7"],
                    )
                button = telegram_markup(_, chat_id)
                run = await app.send_photo(
                    original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                url = check[0].get("url")
                if videoid == "telegram":
                    image = None
                elif videoid == "soundcloud":
                    image = None

                elif "saavn" in videoid:
                    url = check[0].get("url")
                    details = await Platform.saavn.info(url)
                    image = details["thumb"]
                else:
                    try:
                        image = await Platform.youtube.thumbnail(videoid, True)
                    except Exception:
                        image = None
                is_remote = isinstance(queued, str) and queued.startswith("http")
                ffmpeg_params = (_REMOTE_FFMPEG_PARAMS_VIDEO if is_remote else _LOCAL_FFMPEG_PARAMS_VIDEO) if video else (_REMOTE_FFMPEG_PARAMS if is_remote else _LOCAL_FFMPEG_PARAMS)
                if video:
                    stream = MediaStream(
                        queued,
                        audio_parameters=audio_stream_quality,
                        video_parameters=video_stream_quality,
                        ffmpeg_parameters=ffmpeg_params,
                    )
                else:
                    if image and config.PRIVATE_BOT_MODE == str(True):
                        stream = MediaStream(
                            image,
                            audio_path=queued,
                            audio_parameters=audio_stream_quality,
                            video_parameters=video_stream_quality,
                            ffmpeg_parameters=ffmpeg_params,
                        )
                    else:
                        stream = MediaStream(
                            queued,
                            audio_parameters=audio_stream_quality,
                            video_flags=MediaStream.Flags.IGNORE,
                            ffmpeg_parameters=ffmpeg_params,
                        )
                try:
                    await client.play(chat_id, stream, config=call_config)
                except Exception:
                    return await app.send_message(
                        original_chat_id,
                        text=_["call_7"],
                    )
                if videoid == "telegram":
                    button = telegram_markup(_, chat_id)
                    run = await app.send_photo(
                        original_chat_id,
                        photo=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                        caption=_["stream_1"].format(
                            title, config.SUPPORT_GROUP, check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                elif videoid == "soundcloud":
                    button = telegram_markup(_, chat_id)
                    run = await app.send_photo(
                        original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_["stream_1"].format(
                            title, config.SUPPORT_GROUP, check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                elif "saavn" in videoid:
                    button = telegram_markup(_, chat_id)
                    run = await app.send_photo(
                        original_chat_id,
                        photo=image,
                        caption=_["stream_1"].format(title, url, check[0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                else:
                    img = await gen_thumb(videoid)
                    button = stream_markup(_, videoid, chat_id)
                    run = await app.send_photo(
                        original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(
                            title[:27],
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    async def ping(self):
        pings = []
        for call in self.calls:
            pings.append(call.ping)
        if pings:
            return str(round(sum(pings) / len(pings), 3))
        else:
            LOGGER(__name__).error("No active clients for ping calculation.")
            return "No active clients"

    async def start(self):
        """Starts all PyTgCalls instances for the existing userbot clients."""
        LOGGER(__name__).info(f"Starting PyTgCall Clients")
        await asyncio.gather(*[c.start() for c in self.calls])
        await self.decorators() 


    
    async def decorators(self):
        for call in self.calls:

            @call.on_update(filters.chat_update(ChatUpdate.Status.LEFT_CALL))
            async def stream_services_handler(client, update):
                await self.stop_stream(update.chat_id)

            @call.on_update(filters.stream_end())
            async def stream_end_handler(client, update: Update):
                await self.change_stream(client, update.chat_id)


    def __getattr__(self, name):
        if not self.calls:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        first_call = self.calls[0]
        if hasattr(first_call, name):
            return getattr(first_call, name)
        raise AttributeError(f"'{type(first_call).__name__}' object has no attribute '{name}'")


Ayush = Call()
