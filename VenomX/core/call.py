
# All rights reserved.
#
import asyncio
import re
import subprocess
import time
from functools import partial, wraps
from typing import Union

from json import JSONDecodeError
from ntgcalls import FFmpegError, TelegramServerError
from pytgcalls.exceptions import (InvalidVideoProportion, NoActiveGroupCall,
                                  NoAudioSourceFound, NoVideoSourceFound, NotInCallError)
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, filters
from pytgcalls.types import (
    ChatUpdate,
    GroupCallConfig,
    MediaStream,
    Update,
)
from pytgcalls.types.raw import Stream
from pytgcalls.types import Device, StreamEnded
from pyrogram import raw
from VenomX.utils.stream.playback import Playback, current, playback_lock
from VenomX.utils.stream import lyrics

from VenomX.core.media_probe import check_stream

import pytgcalls.ffmpeg as _pytgcalls_ffmpeg
import pytgcalls.types.stream.media_stream as _pytgcalls_media_stream

_PYTGCALLS_SUPPORTED_FLAGS = {}


def _pytgcalls_supported_flags(process: str) -> set:
    cached = _PYTGCALLS_SUPPORTED_FLAGS.get(process)
    if cached is not None:
        return cached
    try:
        result = subprocess.run(
            [process, "-h", "full"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
        output = result.stdout.decode("utf-8", "replace")
    except Exception:
        output = ""
    flags = set()
    for names in re.findall(
        r"(?m)^ *(--?\w[\w-]*(?:, *--?\w[\w-]*)*)",
        output,
    ):
        flags.update(name.strip() for name in names.split(","))
    flags.add("-i")
    _PYTGCALLS_SUPPORTED_FLAGS[process] = flags
    return flags


async def _pytgcalls_cleanup_commands(commands, process_name=None, blacklist=None):
    process = process_name or commands[0]
    supported = _PYTGCALLS_SUPPORTED_FLAGS.get(process)
    if supported is None:
        supported = await asyncio.to_thread(_pytgcalls_supported_flags, process)
    if process == "ffmpeg":
        blacklist = [
            *(blacklist or ()),
            "-reconnect",
            "-reconnect_at_eof",
            "-reconnect_streamed",
            "-reconnect_delay_max",
        ]
    new_commands = []
    ignore_next = False
    for value in commands:
        if not value:
            continue
        is_flag = value[0] == "-" and not value[1:].replace(".", "", 1).isdigit()
        if is_flag:
            ignore_next = value not in supported or (
                blacklist is not None and value in blacklist
            )
        if not ignore_next:
            new_commands.append(value)
        elif not is_flag:
            ignore_next = False
    return new_commands


_pytgcalls_media_stream.check_stream = check_stream
_pytgcalls_ffmpeg.cleanup_commands = _pytgcalls_cleanup_commands
_pytgcalls_media_stream.cleanup_commands = _pytgcalls_cleanup_commands

import config
from strings import get_string
from VenomX.platforms.Youtube import _YT_HTTP_HEADERS
from VenomX import LOGGER, Platform, app, userbot
from VenomX.misc import db
from VenomX.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_active_chats,
    get_audio_bitrate,
    get_instant_play,
    get_lang,
    get_loop,
    get_video_bitrate,
    group_assistant,
    is_active_chat,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from VenomX.utils.exceptions import AssistantErr
from VenomX.utils.rich_panels import replace_panel, spawn_now_playing
from VenomX.utils.rich_msg import RichMystic, send_rich
from VenomX.utils.stream.autoclear import auto_clean
from VenomX.utils.thumbnails import gen_thumb

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChannelsTooMuch,
    ChatAdminRequired,
    ChannelPrivate,
    FloodWait,
    InviteHashExpired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
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

_stop_log_last: dict = {}

# Tracks joins separately so status checks can recognize an in-flight handshake.
_join_locks: dict = {}
MEDIA_ERRORS = (TimeoutError, FileNotFoundError, JSONDecodeError, FFmpegError,
                NoAudioSourceFound, NoVideoSourceFound, InvalidVideoProportion)

# When the bot empties the queue it leaves the call itself; Telegram then
# delivers a LEFT_CALL update that can land AFTER a fresh /play has already
# re-joined — treating that echo as "assistant removed" ran stop_stream and
# kicked the assistant back out mid-play (assistant gone, card alive, no
# audio). Our own recent leaves are stamped and their echo ignored.
_SELF_LEFT_GRACE = 20
_self_left: dict = {}

# How often to compare the in-memory active list against the real calls. This
# is the safety net for VC ends whose LEFT_CALL is never delivered (or gets
# swallowed by the self-leave echo guard above).
_RECONCILE_INTERVAL = int(getattr(config, "VC_STATE_RECONCILE_INTERVAL", 30) or 30)


def _mark_self_left(chat_id: int) -> None:
    _self_left[chat_id] = time.monotonic()


def _was_self_left(chat_id: int) -> bool:
    return time.monotonic() - _self_left.get(chat_id, 0.0) < _SELF_LEFT_GRACE


async def _rollback_join(chat_id: int) -> None:
    """Discard local playback state after a failed connection or state commit."""
    await _clear_(chat_id, "Playback could not start.")


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
_FFMPEG_USER_AGENT = f"-user_agent '{_YT_HTTP_HEADERS['User-Agent']}' "
_REMOTE_FFMPEG_PARAMS = (
    f"{_PROXY_FFMPEG}"
    f"{_FFMPEG_USER_AGENT}"
    "-rw_timeout 15000000 "
    "-analyzeduration 5000000 -probesize 131072 "
    "-fflags +genpts+discardcorrupt "
    "-flags low_delay"
)

# For local files:
_LOCAL_FFMPEG_PARAMS = (
    "-analyzeduration 5000000 -probesize 1000000 "
    "-fflags +genpts+discardcorrupt "
    ""
)

# Video-specific: faster decode + lower buffer for real-time pipe streaming
_REMOTE_FFMPEG_PARAMS_VIDEO = (
    f"{_PROXY_FFMPEG}"
    f"{_FFMPEG_USER_AGENT}"
    "-rw_timeout 15000000 "
    "-analyzeduration 3000000 -probesize 65536 "
    "-fflags +genpts+discardcorrupt+nobuffer "
    "-flags low_delay"
)

_LOCAL_FFMPEG_PARAMS_VIDEO = (
    "-analyzeduration 3000000 -probesize 65536 "
    "-fflags +genpts+discardcorrupt+nobuffer "
    "-flags low_delay"
)


async def _clear_(chat_id, reason="Playback stopped."):
    current.pop(chat_id, None)
    lyrics.stop(chat_id)
    lyrics.forget(chat_id)
    popped = db.pop(chat_id, None)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)
    if popped:
        mid = popped[0].get("rich_mid")
        if mid:
            await replace_panel(chat_id, mid, reason)
        await auto_clean(popped)


async def _chat_has_live_call(chat_id: int, calls) -> bool | None:
    """Whether any of our PyTgCalls clients still holds this chat's call.

    The in-memory `active` list is only a hint: a VC can be ended without us
    seeing a LEFT_CALL (missed update, swallowed echo, assistant switched), and
    a stale hint makes /play append to a queue nobody is playing.
    """
    missing = False
    for client in calls:
        try:
            if chat_id in await client.calls:
                return True
        except Exception:
            missing = True
    return None if missing else False


async def call_presence(chat_id):
    """Return (own participant, total participants), or None for an unknown result."""
    try:
        async with asyncio.timeout(8):
            assistant = await get_assistant(chat_id)
            peer = await assistant.resolve_peer(chat_id)
            if isinstance(peer, raw.types.InputPeerChannel):
                info = await assistant.invoke(raw.functions.channels.GetFullChannel(channel=peer))
            else:
                info = await assistant.invoke(raw.functions.messages.GetFullChat(chat_id=peer.chat_id))
            call = getattr(info.full_chat, "call", None)
            if call is None:
                return None, 0
            snapshot = await assistant.invoke(raw.functions.phone.GetGroupCall(call=call, limit=2))
            count = snapshot.call.participants_count
            participants = snapshot.participants
            if count > len(participants) and not any(p.is_self for p in participants):
                result = await assistant.invoke(raw.functions.phone.GetGroupParticipants(
                    call=call, ids=[raw.types.InputPeerSelf()], sources=[], offset="", limit=1,
                ))
                participants = result.participants
            member = next((p for p in participants if not p.left and
                           (p.is_self or getattr(p.peer, "user_id", None) == assistant.id)), None)
            return member, count
    except Exception as exc:
        LOGGER(__name__).debug("VC membership unknown for %s (%s)", chat_id, type(exc).__name__)
        return None


async def _assistant_still_in_call(chat_id):
    presence = await call_presence(chat_id)
    return None if presence is None else presence[0] is not None


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


def _serialize_playback(method):
    @wraps(method)
    async def locked(self, chat_id, *args, **kwargs):
        async with playback_lock(chat_id):
            return await method(self, chat_id, *args, **kwargs)
    return locked


class Call:
    def __init__(self):
        self.calls = []

        for client in userbot.clients:
            pycall = PyTgCalls(client)
            self.calls.append(pycall)

    def is_join_pending(self, chat_id: int) -> bool:
        lock = _join_locks.get(chat_id)
        return lock is not None and lock.locked()

    async def is_live_chat(self, chat_id: int) -> bool:
        """Active flag AND a real call. Clears stale state when they disagree.

        stream() uses this to decide between appending to the queue and
        starting a fresh session. Without the call check, a chat whose VC ended
        silently keeps looking active and every /play just piles onto a dead
        queue (the song shows "Added to queue at #45" while no assistant is in
        the call).
        """
        if not await is_active_chat(chat_id):
            return False
        lock = _join_locks.get(chat_id)
        if lock is not None and lock.locked():
            return True
        # A previous join may have completed before its queue entry was saved.
        # Start the requested track instead of appending behind a missing head.
        if not db.get(chat_id):
            return False
        native = await _chat_has_live_call(chat_id, self.calls)
        if native is True:
            return True
        if native is None and await _assistant_still_in_call(chat_id) is not False:
            return True
        LOGGER(__name__).info(
            "[Call] stale active chat %s (assistant not in call); clearing queue",
            chat_id,
        )
        await _clear_(chat_id)
        return False

    @_serialize_playback
    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)
        if chat_id in current:
            current[chat_id].pause()

    @_serialize_playback
    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)
        if chat_id in current:
            current[chat_id].resume()

    async def mute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    async def unmute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    @_serialize_playback
    async def stop_stream(self, chat_id: int, reason="Playback stopped."):
        # Cleanup must not depend on resolving the assistant: if that lookup
        # fails, the stale active flag would keep growing the queue forever.
        _mark_self_left(chat_id)
        await _clear_(chat_id, reason)
        try:
            assistant = await group_assistant(self, chat_id)
            await assistant.leave_call(chat_id)
        except Exception as e:
            # A user spamming the skip/close button fires stop_stream every
            # ~2s while the assistant is already out — one line per burst is
            # enough, a traceback wall is not.
            key = ("stop", chat_id)
            now = time.time()
            if now - _stop_log_last.get(key, 0) < 60:
                LOGGER(__name__).debug(
                    "stop stream for chat %s: %s", chat_id, e
                )
            else:
                _stop_log_last[key] = now
                LOGGER(__name__).error(
                    f"Failed to stop stream for chat {chat_id}: {e}"
                )

    @_serialize_playback
    async def force_stop_stream(self, chat_id: int):
        _mark_self_left(chat_id)
        current.pop(chat_id, None)
        lyrics.stop(chat_id)
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

    @_serialize_playback
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

        await self._switch_source(assistant, chat_id, stream, call_config)
        # A skipped-in track just began: its end event must not be mistaken
        # for the replaced track's echo (or the reverse).
        current[chat_id] = Playback(link)
        self._schedule_idle_leave(assistant, chat_id)

    @_serialize_playback
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
                ffmpeg_parameters=f"{proxy_part}-ss {to_seek} -to {duration} -analyzeduration 3000000 -probesize 65536 -fflags +genpts+discardcorrupt+nobuffer -flags low_delay",
            )
            if mode == "video"
            else MediaStream(
                file_path,
                audio_parameters=audio_stream_quality,
                ffmpeg_parameters=f"{proxy_part}-ss {to_seek} -to {duration} -analyzeduration 5000000 -probesize 131072 -fflags +genpts+discardcorrupt -flags low_delay",
                video_flags=MediaStream.Flags.IGNORE,
            )
        )
        LOGGER(__name__).info(
            "[Call] seek_stream chat=%s seek=%s duration=%s mode=%s",
            chat_id, to_seek, duration, mode,
        )
        await self._switch_source(assistant, chat_id, stream, call_config)
        offset = 0
        for part in str(to_seek).split(":"):
            offset = offset * 60 + float(part)
        current[chat_id] = Playback(file_path, offset)
        if db.get(chat_id):
            db[chat_id][0]["played"] = int(offset)

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
        await assistant.play(config.LOGGER_ID, MediaStream(link), config=call_config)
        await asyncio.sleep(0.5)
        await assistant.leave_call(config.LOGGER_ID)

    async def join_chat(self, chat_id, attempts=1):
        max_attempts = len(assistants) - 1
        userbot = await get_assistant(chat_id)
        try:
            language = await get_lang(chat_id)
            _ = get_string(language)
        except Exception:
            _ = get_string("en")
        try:
            member = await app.get_chat_member(chat_id, userbot.id)
        except UserNotParticipant:
            pass
        except ChatAdminRequired:
            raise AssistantErr(_["call_1"])
        except Exception as e:
            LOGGER(__name__).exception(
                "[Call] membership check failed for chat %s (%s)",
                chat_id, type(e).__name__,
            )
            raise AssistantErr(_["call_3"].format(f"{type(e).__name__}: {e}"))
        else:
            if member.status == ChatMemberStatus.BANNED:
                raise AssistantErr(_["call_2"].format(userbot.username, userbot.id))
            if member.status != ChatMemberStatus.LEFT:
                return False
        try:
            chat = await app.get_chat(chat_id)
        except ChatAdminRequired:
            raise AssistantErr(_["call_1"])
        except Exception as e:
            raise AssistantErr(_["call_3"].format(f"{type(e).__name__}: {e}"))
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
                        _["call_3"].format(f"{type(e).__name__}: {e}")
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
            if time < 20 and attempts == 1:
                await asyncio.sleep(time)
                attempts += 1
                return await self.join_chat(chat_id, attempts)
            else:
                if attempts <= max_attempts:
                    attempts += 1
                    userbot = await set_assistant(chat_id)
                    return await self.join_chat(chat_id, attempts)

                raise AssistantErr(_["call_10"].format(time))
        except ChannelPrivate as e:
            links.pop(chat_id, None)
            if attempts <= max_attempts:
                attempts += 1
                return await self.join_chat(chat_id, attempts)
            raise AssistantErr(
                _["call_3"].format(
                    "assistant cannot resolve/join this chat (stale invite "
                    f"link or access): {e}"
                )
            )
        except Exception as e:
            # Surface the full traceback: the invite-path errors were only
            # ever reported as their class name, hiding real causes.
            LOGGER(__name__).exception(
                "[Call] join_chat failed for chat %s (%s)", chat_id, type(e).__name__
            )
            # Common join denials deserve plain words, not a class name.
            friendly = {
                "ChatWriteForbidden": (
                    "assistant can't write in this chat — make it admin"
                ),
                "UserBannedInChannel": "assistant is banned in this chat",
                "ChatIdInvalid": (
                    "chat id invalid — add the bot to the group again"
                ),
            }.get(type(e).__name__)
            if friendly:
                raise AssistantErr(_["call_3"].format(friendly))
            raise AssistantErr(_["call_3"].format(f"{type(e).__name__}: {e}"))
        return True

    async def _prepare_stream(self, chat_id, stream):
        started = time.monotonic()
        try:
            async with asyncio.timeout(48):
                await stream.check_stream()
        except TimeoutError as exc:
            LOGGER(__name__).warning("[Call] media probe timed out chat=%s elapsed=%.1fs",
                                     chat_id, time.monotonic() - started)
            raise FFmpegError("Media probe timed out") from exc
        if stream.microphone is None and stream.camera is None and stream.screen is None:
            raise FFmpegError("No playable media tracks")
        return Stream(stream.microphone, stream.speaker, stream.camera, stream.screen)

    async def _switch_source(self, client, chat_id, stream, call_config):
        prepared = await self._prepare_stream(chat_id, stream)
        try:
            async with asyncio.timeout(28):
                await client.play(chat_id, prepared, config=call_config)
        except (TimeoutError, asyncio.CancelledError) as exc:
            try:
                await self._reset_stale_call(client, chat_id)
            finally:
                await _rollback_join(chat_id)
            if isinstance(exc, TimeoutError):
                raise AssistantErr("Voice connection timed out.") from exc
            raise

    async def _reset_stale_call(self, client, chat_id):
        try:
            async with asyncio.timeout(6):
                await client.leave_call(chat_id)
        except NotInCallError:
            # _connect_call can stop the native binding before raising.
            # Its public leave then returns before sending the MTProto leave.
            async with asyncio.timeout(6):
                if await _assistant_still_in_call(chat_id) is True:
                    await client._app.leave_group_call(chat_id)
        except NoActiveGroupCall:
            pass
        except Exception as exc:
            LOGGER(__name__).warning("[Call] leave failed chat=%s error=%s", chat_id, type(exc).__name__)
            raise

    @_serialize_playback
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
            async with asyncio.timeout(80):
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

        prepared = await self._prepare_stream(chat_id, stream)
        self._cancel_idle_leave(chat_id)
        started = _t.monotonic()
        LOGGER(__name__).info("[Call] media ready chat=%s elapsed=%.1fs", chat_id, started - _j0)
        try:
            async with asyncio.timeout(28):
                if chat_id not in current and chat_id in await assistant.calls:
                    if await _assistant_still_in_call(chat_id) is False:
                        await self._reset_stale_call(assistant, chat_id)
                try:
                    await assistant.play(chat_id, prepared, config=call_config)
                except (UserNotParticipant, ChannelPrivate, NoActiveGroupCall):
                    if not await self.join_chat(chat_id):
                        raise
                    assistant = await group_assistant(self, chat_id)
                    await assistant.play(chat_id, prepared, config=call_config)
            await add_active_chat(chat_id)
            await music_on(chat_id)
            if video:
                await add_active_video_chat(chat_id)
        except (Exception, asyncio.CancelledError) as exc:
            LOGGER(__name__).warning("[Call] voice join failed chat=%s elapsed=%.1fs error=%s",
                                     chat_id, _t.monotonic() - started, type(exc).__name__)
            try:
                await self._reset_stale_call(assistant, chat_id)
            except Exception as cleanup_error:
                LOGGER(__name__).warning("[Call] cleanup incomplete chat=%s error=%s",
                                         chat_id, type(cleanup_error).__name__)
            await _rollback_join(chat_id)
            if isinstance(exc, TimeoutError):
                raise AssistantErr("**Voice connection timed out. Please try again.**") from exc
            if isinstance(exc, NoActiveGroupCall):
                raise AssistantErr("**No active voice chat found.**") from exc
            if isinstance(exc, TelegramServerError):
                raise AssistantErr("**Telegram could not connect the assistant. Please try again.**") from exc
            raise
        LOGGER(__name__).info("[Call] voice connected chat=%s elapsed=%.1fs", chat_id, _t.monotonic() - started)
        current[chat_id] = Playback(link)
        self._schedule_idle_leave(assistant, chat_id)

    async def warm_join(self, chat_id):
        """Warm the selected assistant's peer resolution without mutating call state."""
        try:
            async with asyncio.timeout(5):
                assistant = await group_assistant(self, chat_id)
                await assistant.resolve_chat_id(chat_id)
        except Exception as e:
            LOGGER(__name__).debug("warm_join for %s skipped: %s", chat_id, e)

    async def _delayed_leave(self, client, chat_id, delay=None):
        await asyncio.sleep(delay if delay is not None else VC_IDLE_GRACE)
        async with playback_lock(chat_id):
            if db.get(chat_id):
                return
            try:
                await client.leave_call(chat_id, close=False)
                _mark_self_left(chat_id)
                LOGGER(__name__).info("[Call] idle leave done for chat %s", chat_id)
            except Exception as e:
                LOGGER(__name__).error(f"Failed idle leave for chat {chat_id}: {e}")
            finally:
                # We are out of the call: drop the active flag too, otherwise the
                # next /play queues behind a call that no longer exists.
                await _clear_(chat_id)
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

    async def change_stream(self, client, chat_id, *, ended=False):
        source = current.get(chat_id)
        async with playback_lock(chat_id):
            if source is None or current.get(chat_id) is not source:
                return
            if await group_assistant(self, chat_id) is not client:
                return
            if not db.get(chat_id):
                if ended:
                    LOGGER(__name__).info("[Call] audio ended with empty queue chat=%s; leaving", chat_id)
                    self._cancel_idle_leave(chat_id)
                    _mark_self_left(chat_id)
                    try:
                        await self._reset_stale_call(client, chat_id)
                    finally:
                        await _clear_(chat_id, "Playback ended.")
                return
            entry = db[chat_id][0]
            elapsed = int(source.position())
            duration = entry.get("seconds", 0)
            age = time.monotonic() - source.started if source.started is not None else None
            if ended and source.recovered and age is not None and age < 15:
                LOGGER(__name__).info(
                    "[Call] recovered stream_end echo ignored for chat=%s track=%s age=%.1fs elapsed=%ss",
                    chat_id, entry.get("vidid"), age, elapsed,
                )
                return
            early = ended and duration and elapsed + 10 < duration
            LOGGER(__name__).info("[Call] audio ended chat=%s track=%s elapsed=%s duration=%s",
                                  chat_id, entry.get("vidid"), elapsed, duration)
            if early and not source.recovered and source.started is not None:
                source.recovered = True
                # Re-open a truncated finite source once at the last playing position.
                try:
                    await self.seek_stream(chat_id, source.source, elapsed, entry["dur"], entry["streamtype"])
                except Exception as exc:
                    LOGGER(__name__).warning("[Call] source recovery failed chat=%s (%s)", chat_id, type(exc).__name__)
                else:
                    current[chat_id].recovered = True
                    return
            if early:
                await set_loop(chat_id, 0)
            lyrics.stop(chat_id)
            try:
                await self._advance_queue(client, chat_id)
            finally:
                if current.get(chat_id) is source:
                    await self.stop_stream(chat_id, "Could not start the next track.")

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
                if popped and popped.get("rich_mid"):
                    await replace_panel(chat_id, popped["rich_mid"], "Playback ended.")
                else:
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
                    await self._switch_source(client, chat_id, stream, call_config)
                    current[chat_id] = Playback(link)
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
                from VenomX.utils.stream.stream import play_youtube_source
                image = None
                if not video and config.PRIVATE_BOT_MODE == str(True):
                    try:
                        image = await Platform.youtube.thumbnail(videoid, True)
                    except Exception:
                        pass
                try:
                    stream_link = await play_youtube_source(
                        videoid, video, mystic,
                        partial(self.skip_stream, chat_id, video=video, image=image),
                        instant=await get_instant_play(chat_id),
                    )
                except Exception:
                    await _drop_old_card(old_mystic)
                    return await mystic.edit_text(_["call_7"])
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
                    await self._switch_source(client, chat_id, stream, call_config)
                    current[chat_id] = Playback(play_source)
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
                    await self._switch_source(client, chat_id, stream, call_config)
                    current[chat_id] = Playback(queued)
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
                chat_id = update.chat_id
                if await group_assistant(self, chat_id) is not client:
                    return
                source = current.get(chat_id)
                async with playback_lock(chat_id):
                    if source is not None and current.get(chat_id) is not source:
                        return
                    still_in = await _assistant_still_in_call(chat_id)
                    if still_in is not False:
                        LOGGER(__name__).info(
                            "[Call] LEFT_CALL echo ignored for chat %s", chat_id
                        )
                        return
                    LOGGER(__name__).info("[Call] VC left chat=%s status=%s", chat_id, update.status)
                    await _clear_(chat_id, "Playback stopped. The assistant left the voice chat.")

            @call.on_update(filters.stream_end(StreamEnded.Type.AUDIO, Device.MICROPHONE))
            async def stream_end_handler(client, update: Update):
                LOGGER(__name__).info(
                    "[Call] stream_end update chat=%s type=%s device=%s",
                    update.chat_id, update.stream_type, update.device,
                )
                await self.change_stream(client, update.chat_id, ended=True)


    def __getattr__(self, name):
        if not self.calls:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        first_call = self.calls[0]
        if hasattr(first_call, name):
            return getattr(first_call, name)
        raise AttributeError(f"'{type(first_call).__name__}' object has no attribute '{name}'")


Ayush = Call()
