"""Reconcile Telegram membership and the outgoing stream with the local queue."""
import asyncio
import time

from VenomX import LOGGER
from VenomX.core.call import Ayush, call_presence
from VenomX.utils.database import is_autoend
from VenomX.utils.stream.playback import current, playback_lock


_LOST_GRACE = 10


async def inspect_call(chat_id, source, observations):
    if playback_lock(chat_id).locked():
        return
    if current.get(chat_id) is not source:
        observations.pop(chat_id, None)
        return
    presence = await call_presence(chat_id)
    if presence is None:
        observations.pop(chat_id, None)
        return
    member, count = presence
    if member is None:
        reason, grace = "Voice connection was lost.", _LOST_GRACE
    elif member.muted and not member.can_self_unmute:
        reason, grace = "Assistant remained muted for one minute.", 60
    elif count == 1 and await is_autoend():
        reason, grace = "Playback ended because no listeners remained.", 30
    else:
        observations.pop(chat_id, None)
        return

    now = time.monotonic()
    previous = observations.get(chat_id)
    if previous is None or previous[:2] != (source, reason):
        observations[chat_id] = (source, reason, now)
        LOGGER(__name__).info("[Call] monitor chat=%s state=%s", chat_id, reason)
        return
    if now - previous[2] < grace:
        return
    observations.pop(chat_id, None)
    if playback_lock(chat_id).locked() or current.get(chat_id) is not source:
        return
    async with playback_lock(chat_id):
        if current.get(chat_id) is source:
            LOGGER(__name__).info("[Call] chat=%s %s", chat_id, reason)
            await Ayush.stop_stream(chat_id, reason)


async def monitor_calls():
    observations = {}
    while True:
        await asyncio.sleep(10)
        for chat_id in observations.keys() - current.keys():
            observations.pop(chat_id)
        for chat_id, source in list(current.items()):
            try:
                await inspect_call(chat_id, source, observations)
            except Exception as exc:
                observations.pop(chat_id, None)
                LOGGER(__name__).warning("VC check failed chat=%s (%s)", chat_id, type(exc).__name__)


asyncio.create_task(monitor_calls(), name="monitor_calls")
