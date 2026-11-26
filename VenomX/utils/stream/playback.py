"""The source currently feeding a chat, and its pause-aware media clock."""
import asyncio
import time
from dataclasses import dataclass, field
from weakref import WeakValueDictionary


@dataclass(eq=False)
class Playback:
    source: str
    offset: float = 0
    started: float | None = field(default_factory=time.monotonic)
    recovered: bool = False

    def position(self):
        return self.offset if self.started is None else self.offset + time.monotonic() - self.started

    def pause(self):
        self.offset = self.position()
        self.started = None

    def resume(self):
        if self.started is None:
            self.started = time.monotonic()


current: dict[int, Playback] = {}
_locks = WeakValueDictionary()


class _PlaybackLock(asyncio.Lock):
    """Allow nested playback operations only within the owning asyncio task."""

    def __init__(self):
        super().__init__()
        self.owner = None
        self.depth = 0

    async def __aenter__(self):
        task = asyncio.current_task()
        if self.owner is not task:
            await self.acquire()
            self.owner = task
        self.depth += 1
        return self

    async def __aexit__(self, *args):
        self.depth -= 1
        if self.depth == 0:
            self.owner = None
            self.release()


def playback_lock(chat_id):
    return _locks.setdefault(chat_id, _PlaybackLock())
