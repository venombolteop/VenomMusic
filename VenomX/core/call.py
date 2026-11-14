
# All rights reserved.
#
import asyncio
import time
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
from VenomX.utils.rich_panels import spawn_now_playing
from VenomX.utils.rich_msg import RichMystic, send_rich
from VenomX.utils.stream.autoclear import auto_clean
from VenomX.utils.thumbnails import gen_thumb

from pyrogram.errors import (
    ChannelsTooMuch,
    ChatAdminRequired,
    FloodWait,
    InviteHashExpired,
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


# How long the assistant stays in the voice chat after the queue empties.
# Leaving immediately means every next /play pays the full group-call
# handshake (~15s: join + key exchange + confirm_call). Staying put makes the
# next track a stream swap instead, which is sub-second.
VC_IDLE_GRACE = int(getattr(config, "VC_IDLE_GRACE", 600) or 600)
_idle_leave_tasks = {}

# stream_end for a video track can fire twice (audio and video source ends
# reported separately), and the two change_stream() runs then race: each pops
# its own queue head, the second play() call replaces the first, and the user
# sees the second queued song instead of the first plus a doubled
# "downloading your next song" card. A per-chat lock serialises runs and a
# short dedup window throws away the echo.
_END_DEDUP_WINDOW = 2.5
_end_locks: dict = {}
_end_last: dict = {}

# Two /play commands landing on the same chat within the ~13s group-call
# handshake used to race each other into join_call: both saw "not active",
# the second wiped the first track's queue and started its own join, and the
# result was a card with no audio (only lyrics) or an assistant that never
# appeared. join_call is serialised per chat, the chat is marked active
# BEFORE the handshake so a second play queues itself instead of racing, and
# the active flag is rolled back if the join actually fails.
_join_locks: dict = {}

# When the bot empties the queue it leaves the call itself; Telegram then
# delivers a LEFT_CALL update that can land AFTER a fresh /play has already
# re-joined — treating that echo as "assistant removed" ran stop_stream and
# kicked the assistant back out mid-play (assistant gone, card alive, no
# audio). Our own recent leaves are stamped and their echo ignored.
_SELF_LEFT_GRACE = 20
_self_left: dict = {}


def _mark_self_left(chat_id: int) -> None:
    _self_left[chat_id] = time.monotonic()


def _was_self_left(chat_id: int) -> bool:
    return time.monotonic() - _self_left.get(chat_id, 0.0) < _SELF_LEFT_GRACE


async def _rollback_join(chat_id: int) -> None:
    """Undo the pre-handshake active-marking when the join truly fails.

    Without this a failed join leaves the chat 'active' and every following
    /play silently queues behind a call that nobody is in.
    """
    from VenomX.utils.stream.autoclear import auto_clean as _ac

    try:
        popped = db.pop(chat_id, None)
        if popped:
            await _ac(popped)
        db[chat_id] = []
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
    except Exception:  # noqa: BLE001
        LOGGER(__name__).warning("[Call] rollback_join cleanup failed for %s", chat_id)

def _needs_proxy(link) -> bool:
    """Only external remote URLs need the ffmpeg proxy.

    The media API serves a permalink on this box (127.0.0.1) — routing that
    through the WARP proxy breaks playback.
    """
    if not isinstance(link, str) or not link.startswith("http"):
        return False
    return not any(host in link for host in ("127.0.0.1", "localhost", "[::1]"))

# ffmpeg parameters for remote URLs (YouTube direct streams via proxy).
# -reconnect flags BREAK through HTTP proxies — removed.
# IMPORTANT: only INPUT-side options allowed here — pytgcalls places these
# before the input file. Output/encoder options (-acodec/-ar/-vn etc.) will
# crash ffmpeg with "Option not found" and kill the stream instantly.
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
    "-analyzeduration 5000000 -probesize 1000000 "
    "-fflags +genpts+discardcorrupt "
    ""
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


async def _drop_old_card(mystic) -> None:
    """Retire the previous now-playing/status card (delete is best effort)."""
    if mystic is None:
        return
    try:
        await mystic.delete()
    except Exception:
        pass


async def _spawn_then_clean(_, chat_id, old_mystic, *spawn_args, **spawn_kw):
    """Spawn the next now-playing card while the OLD reply anchor is still
    alive, and only then delete the previous card — the same order stream()
    uses. Deleting first (the old behaviour in _advance_queue) left the
    anchor dead at send time, so queued tracks shipped plain emoji.
    """
    mid_np = await spawn_now_playing(_, chat_id, *spawn_args, **spawn_kw)
    await _drop_old_card(old_mystic)
    return mid_np


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
        await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    async def mute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    async def unmute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

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
        import time as _t
        _j0 = _t.monotonic()
        self._cancel_idle_leave(chat_id)
        # Arm the advance dedup: the replaced stream's echo must not pop the
        # just-started track within the dedup window afterwards.
        _end_last[chat_id] = _t.monotonic()
        assistant = await group_assistant(self, chat_id)
        LOGGER(__name__).info("[Call] join_call: group_assistant %.1fs", _t.monotonic() - _j0)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = await get_video_bitrate(chat_id)
        call_config = GroupCallConfig(auto_start=False)
        is_remote = _needs_proxy(link)
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
        self._schedule_idle_leave(assistant, chat_id)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = await get_video_bitrate(chat_id)
        call_config = GroupCallConfig(auto_start=False)
        is_remote = _needs_proxy(file_path)
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
            try:
                await userbot.join_chat(invitelink)
            except AttributeError:
                pass  # pyroblack parse bug
        except InviteRequestSent:
            # The assistant can't join until approved — do it on the bot's
            # side instead of erroring out: after approval the upcoming
            # retry play should just work on join-request-restricted groups.
            try:
                await app.approve_chat_join_request(chat_id, userbot.id)
                await asyncio.sleep(1.5)
            except Exception as e:
                raise AssistantErr(_["call_3"].format(type(e).__name__))
        except UserAlreadyParticipant:
            pass
        except InviteHashExpired:
            # Cached invite links die (old link revocation); a re-export on
            # the next attempt heals the join instead of erroring the user.
            links.pop(chat_id, None)
            if attempts <= max_attempts:
                attempts += 1
                return await self.join_chat(chat_id, attempts)
            raise AssistantErr(_["call_3"].format(type(InviteHashExpired).__name__))
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
            # Surface the full traceback: the invite-path errors were only
            # ever reported as their class name, hiding real causes.
            LOGGER(__name__).exception(
                "[Call] join_chat failed for chat %s (%s)", chat_id, type(e).__name__
            )
            raise AssistantErr(_["call_3"].format(type(e).__name__))

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        # Serialise joins per chat: a second /play that lands while the
        # ~13s handshake is running must queue, not race.
        lock = _join_locks.setdefault(chat_id, asyncio.Lock())
        async with lock:
            return await self._join_call_locked(
                chat_id, original_chat_id, link, video, image
            )

    async def _join_call_locked(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        import time as _t
        _j0 = _t.monotonic()
        self._cancel_idle_leave(chat_id)
        # Mark the chat active BEFORE the handshake so concurrent plays see an
        # active chat and push into the queue instead of racing the join.
        # Rolled back if the join actually fails below.
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        assistant = await group_assistant(self, chat_id)
        LOGGER(__name__).info("[Call] join_call: group_assistant %.1fs", _t.monotonic() - _j0)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = await get_video_bitrate(chat_id)
        call_config = GroupCallConfig(auto_start=False)
        is_remote = _needs_proxy(link)
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

        LOGGER(__name__).info("[Call] join_call: MediaStream built at %.1fs", _t.monotonic() - _j0)
        try:
            await assistant.play(
                chat_id=chat_id,
                stream=stream,
                config=call_config,
            )
            LOGGER(__name__).info("[Call] join_call: assistant.play done at %.1fs", _t.monotonic() - _j0)
        except Exception:
            # The first play() failure type is the single most useful signal
            # for the "No Active Voice Chat Found" report — surface it.
            LOGGER(__name__).warning(
                "[Call] join_call: first assistant.play failed on chat %s",
                chat_id,
                exc_info=True,
            )
            await self.join_chat(chat_id)
            # A freshly invited assistant may not have seen the group call in
            # its update stream yet — settle before believing the VC is off.
            for _settle in (0.6, 2.5, 6.0):
                await asyncio.sleep(_settle)
                try:
                    await assistant.play(
                        chat_id=chat_id,
                        stream=stream,
                        config=call_config,
                    )
                    break
                except AlreadyJoinedError:
                    await _rollback_join(chat_id)
                    raise AssistantErr(
                        "**ASSISTANT IS ALREADY IN VOICECHAT **\n\nMusic bot system detected that assistant is already in the voicechat, if the problem continues restart the videochat and try again."
                    )
                except TelegramServerError:
                    await _rollback_join(chat_id)
                    raise AssistantErr(
                        "**TELEGRAM SERVER ERROR**\n\nPlease restart Your voicechat."
                    )
                except Exception as e:
                    LOGGER(__name__).warning(
                        f"[Call] retry play after join failed at settle={_settle}: {type(e).__name__}: {e}"
                    )
            else:
                LOGGER(__name__).error(
                    "[Call] join_call: retries exhausted on chat %s", chat_id
                )
                await _rollback_join(chat_id)
                raise AssistantErr(
                    "**No Active Voice Chat Found**\n\nPlease make sure group's voice chat is enabled. If already enabled, please end it and start fresh voice chat again and if the problem continues, try /restart"
                )

        except AlreadyJoinedError:
            # The assistant is already in the call: the behaviour users need
            # is a clean source switch, not an error splash. A short settle
            # then replay also heals the mid-handshake "mic off / silent"
            # state left over from racing plays.
            LOGGER(__name__).info(
                "[Call] AlreadyJoinedError on first play for chat %s; settle+replay", chat_id
            )
            await asyncio.sleep(0.75)
            try:
                await assistant.play(chat_id=chat_id, stream=stream, config=call_config)
            except Exception as e:
                LOGGER(__name__).warning(
                    "[Call] replay after AlreadyJoinedError failed for chat %s: %s: %s",
                    chat_id, type(e).__name__, e,
                )
                raise AssistantErr(
                    "**ASSISTANT IS ALREADY IN VOICECHAT **\n\nMusic bot system detected that assistant is already in the voicechat, if the problem continues restart the videochat and try again."
                )
        except TelegramServerError:
            await _rollback_join(chat_id)
            raise AssistantErr(
                "**TELEGRAM SERVER ERROR**\n\nPlease restart Your voicechat."
            )
        self._schedule_idle_leave(assistant, chat_id)

    async def warm_join(self, chat_id):
        """Resolve the peer and the active group call ahead of the real join.

        Both round trips are Telegram-side, so doing them while the stream URL
        is being resolved hides most of the handshake latency.
        """
        try:
            assistant = await group_assistant(self, chat_id)
            if chat_id in await assistant._binding.calls():
                return
            resolved = await assistant.resolve_chat_id(chat_id)
            await assistant._app.get_input_call(resolved)
            assistant._cache_user_peer.put(resolved, assistant._cache_local_peer)
        except Exception as e:
            LOGGER(__name__).debug("warm_join for %s skipped: %s", chat_id, e)

    async def _delayed_leave(self, client, chat_id, delay=None):
        await asyncio.sleep(delay if delay is not None else VC_IDLE_GRACE)
        if db.get(chat_id):
            return
        try:
            await client.leave_call(chat_id, close=False)
            _mark_self_left(chat_id)
            LOGGER(__name__).info("[Call] idle leave done for chat %s", chat_id)
        except Exception as e:
            LOGGER(__name__).error(f"Failed idle leave for chat {chat_id}: {e}")
        _idle_leave_tasks.pop(chat_id, None)

    def _cancel_idle_leave(self, chat_id):
        task = _idle_leave_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    def _schedule_idle_leave(self, client, chat_id, delay=None):
        # Feature toggle (AUTO_LEAVING_ASSISTANT) with the timer from
        # AUTO_LEAVE_ASSISTANT_TIME; disabled by default, like upstream.
        if getattr(config, "AUTO_LEAVING_ASSISTANT", "False") != str(True):
            return
        self._cancel_idle_leave(chat_id)
        _idle_leave_tasks[chat_id] = asyncio.create_task(
            self._delayed_leave(client, chat_id, delay)
        )

    async def change_stream(self, client, chat_id):
        lock = _end_locks.setdefault(chat_id, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            if now - _end_last.get(chat_id, 0.0) < _END_DEDUP_WINDOW:
                LOGGER(__name__).info(
                    "[Call] duplicate stream_end suppressed for chat %s", chat_id
                )
                return
            _end_last[chat_id] = now
            await self._advance_queue(client, chat_id)

    async def _advance_queue(self, client, chat_id):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        # Empty/missing queue: nothing to play next. Leave quietly instead of
        # raising (a stale stream_end can arrive while a new track is joining).
        if not check:
            await _clear_(chat_id)
            # Leave for real: keeping the assistant in the call makes the next
            # /play take py-tgcalls' set_stream_sources path, which switches the
            # source without restarting ffmpeg, so the chat hears silence.
            self._cancel_idle_leave(chat_id)
            _mark_self_left(chat_id)
            try:
                await client.leave_call(chat_id, close=False)
            except Exception as e:
                LOGGER(__name__).error(f"Failed to leave call for empty queue chat {chat_id}: {e}")
            return
        try:
            old_mystic = None
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            if popped:
                await auto_clean(popped)
                # Deletion of the old card is deferred to _spawn_then_clean:
                # it must happen AFTER the next card is sent, so the reply
                # anchor is still a live message at that moment.
                old_mystic = popped.get("mystic")
            if not check:
                await _drop_old_card(old_mystic)
                await _clear_(chat_id)
                _mark_self_left(chat_id)
                try:
                    await client.leave_call(chat_id, close=False)
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to leave call for chat {chat_id}: {e}")
                return
        except Exception as e:
            LOGGER(__name__).error(f"Error in change_stream for chat {chat_id}: {e}")
            try:
                await _clear_(chat_id)
                _mark_self_left(chat_id)
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
                    await _drop_old_card(old_mystic)
                    return await send_rich(original_chat_id, f"<p>{_['call_7']}</p>")
                is_remote = _needs_proxy(link)
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
                    await _drop_old_card(old_mystic)
                    return await send_rich(original_chat_id, f"<p>{_['call_7']}</p>")
                mid_np = await _spawn_then_clean(
                    _, chat_id, old_mystic, None, title, check[0]["dur"], user,
                    thumb=await gen_thumb(videoid),
                )
            elif "vid_" in queued:
                video = True if str(streamtype) == "video" else False
                rich_mid = await send_rich(original_chat_id, f"<p>{_['call_8']}</p>")
                mystic = RichMystic(original_chat_id, rich_mid)
                # Same fast path stream() uses: the media API permalink streams
                # without a download. The yt-dlp direct URL below is IP-bound to
                # the proxy and answers 403, so it only ever fell through to a
                # full download of the next track.
                from VenomX.utils.stream.stream import _api_stream_url
                stream_link = await _api_stream_url(videoid, video)
                if stream_link:
                    if str(stream_link).startswith("http"):
                        import aiohttp
                        try:
                            async with aiohttp.ClientSession() as _sess:
                                # Range request to trigger API cold-start & validate stream viability
                                async with _sess.get(stream_link, headers={"Range": "bytes=0-1024"}, timeout=10) as _resp:
                                    if _resp.status >= 400:
                                        stream_link = None  # API Failed -> Fallback to yt-dlp
                        except Exception:
                            stream_link = None  # Timeout/Offline -> Fallback to yt-dlp
                    else:
                        import os
                        if not os.path.exists(stream_link):
                            stream_link = None
                n = 1 if stream_link else 0
                if n == 0:
                    try:
                        stream_link, direct = await Platform.youtube.download(
                            videoid,
                            mystic,
                            videoid=True,
                            video=video,
                        )
                    except Exception:
                        await _drop_old_card(old_mystic)
                        return await mystic.edit_text(
                            _["call_7"], disable_web_page_preview=True
                        )
                is_remote = _needs_proxy(stream_link)
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
                    await _drop_old_card(old_mystic)
                    return await send_rich(original_chat_id, f"<p>{_['call_7']}</p>")
                try:
                    # Precise "via" tag for the card — the db entry only gets a
                    # guess at queue time, this overwrites it with the truth.
                    from VenomX.utils.stream.stream import _play_source_tag
                    db[chat_id][0]["source"] = _play_source_tag(stream_link)
                except Exception:
                    pass
                # Spawn first (the status card is still a live reply anchor),
                # THEN retire the old cards — deletion order is what keeps
                # premium emoji on queued tracks.
                mid_np = await _spawn_then_clean(
                    _, chat_id, old_mystic, videoid, title, check[0]["dur"], user,
                    thumb=await gen_thumb(videoid),
                )
                if 'mystic' in locals():
                    await mystic.delete()
            elif "index_" in queued:
                # A queued playlist item arrives as a downloaded file path.
                # Streaming the permalink instead means the next track starts
                # when the previous one ends rather than after another fetch.
                play_source = videoid
                if video is not None and not str(videoid).startswith("http"):
                    try:
                        from VenomX.utils.stream.stream import _api_stream_url
                        permalink = await _api_stream_url(
                            check[0].get("vidid"), bool(video)
                        )
                        if permalink and check[0].get("vidid") not in (
                            None, "", "telegram"
                        ):
                            play_source = permalink
                    except Exception as e:
                        LOGGER(__name__).debug(
                            "playlist permalink unavailable: %s: %s",
                            type(e).__name__, e,
                        )
                is_remote = _needs_proxy(play_source)
                ffmpeg_params = (_REMOTE_FFMPEG_PARAMS_VIDEO if is_remote else _LOCAL_FFMPEG_PARAMS_VIDEO) if video else (_REMOTE_FFMPEG_PARAMS if is_remote else _LOCAL_FFMPEG_PARAMS)
                stream = (
                    MediaStream(
                        play_source,
                        audio_parameters=audio_stream_quality,
                        video_parameters=video_stream_quality,
                        ffmpeg_parameters=ffmpeg_params,
                    )
                    if str(streamtype) == "video"
                    else MediaStream(
                        play_source,
                        audio_parameters=audio_stream_quality,
                        video_flags=MediaStream.Flags.IGNORE,
                        ffmpeg_parameters=ffmpeg_params,
                    )
                )
                try:
                    await client.play(chat_id, stream, config=call_config)
                except Exception:
                    await _drop_old_card(old_mystic)
                    return await send_rich(original_chat_id, f"<p>{_['call_7']}</p>")
                try:
                    from VenomX.utils.stream.stream import _play_source_tag
                    db[chat_id][0]["source"] = _play_source_tag(play_source)
                except Exception:
                    pass
                mid_np = await _spawn_then_clean(
                    _, chat_id, old_mystic, None, title, check[0]["dur"], user,
                    thumb=config.STREAM_IMG_URL,
                )
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
                is_remote = _needs_proxy(queued)
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
                    await _drop_old_card(old_mystic)
                    return await send_rich(original_chat_id, f"<p>{_['call_7']}</p>")
                if videoid == "telegram":
                    mid_np = await _spawn_then_clean(
                        _, chat_id, old_mystic, None, title, check[0]["dur"], user,
                        thumb=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                    )
                elif videoid == "soundcloud":
                    mid_np = await _spawn_then_clean(
                        _, chat_id, old_mystic, None, title, check[0]["dur"], user,
                        thumb=config.SOUNCLOUD_IMG_URL,
                    )
                elif "saavn" in videoid:
                    mid_np = await _spawn_then_clean(
                        _, chat_id, old_mystic, None, title, check[0]["dur"], user,
                        thumb=image,
                    )

                else:
                    img = await gen_thumb(videoid)
                    mid_np = await _spawn_then_clean(
                        _, chat_id, old_mystic, videoid, title, check[0]["dur"], user,
                        thumb=img,
                    )

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
                # Careless echo protection: a LEFT_CALL that is the shadow of
                # our OWN recent leave (empty queue) must not run stop_stream
                # if a fresh /play has already re-joined — that used to kick
                # the assistant back out mid-song.
                if _was_self_left(update.chat_id):
                    _self_left.pop(update.chat_id, None)
                    LOGGER(__name__).info(
                        "[Call] LEFT_CALL echo of our own leave ignored for chat %s",
                        update.chat_id,
                    )
                    return
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
