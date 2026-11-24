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


def playback_lock(chat_id):
    return _locks.setdefault(chat_id, asyncio.Lock())
