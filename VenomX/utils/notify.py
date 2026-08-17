
# Centralized error notification to bot owner.
# Uses lazy imports to avoid circular dependency issues.
#

import asyncio
import logging
import time
import traceback
from functools import wraps

_TAG = "ErrorNotifier"

# Dedup window: same error message won't be re-sent within this many seconds.
_dedup: dict[str, float] = {}
DEDUP_SECONDS = 120


def _format_error(tag: str, error: Exception, context: str = "") -> str:
    """Build a concise Telegram-safe error message."""
    err_type = type(error).__name__
    err_msg = str(error)[:500]
    lines = [
        f"🔴 <b>{tag}</b>",
        f"<b>Error:</b> <code>{err_type}</code>",
        f"<b>Message:</b> <code>{err_msg}</code>",
    ]
    if context:
        lines.append(f"<b>Context:</b> {context[:300]}")
    # Append a short traceback (last 5 frames)
    tb = traceback.format_exception(type(error), error, error.__traceback__)
    tail = "".join(tb[-5:]).strip()[:600]
    if tail:
        lines.append(f"<b>Traceback:</b>\n<pre>{tail}</pre>")
    lines.append(f"<code>{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}</code>")
    return "\n".join(lines)


async def notify_owner(tag: str, error: Exception, context: str = ""):
    """Send error details to the bot owner via DM. Non-blocking, never raises."""
    try:
        # Lazy import to avoid circular deps
        from config import OWNER_ID
        from VenomX import app

        msg = _format_error(tag, error, context)

        # Dedup: skip if same error sent recently
        err_type = type(error).__name__
        dedup_key = f"{tag}:{err_type}:{str(error)[:100]}"
        now = time.monotonic()
        if dedup_key in _dedup and now - _dedup[dedup_key] < DEDUP_SECONDS:
            return
        _dedup[dedup_key] = now

        # Clean old dedup entries periodically
        if len(_dedup) > 200:
            stale = [k for k, v in _dedup.items() if now - v > DEDUP_SECONDS * 2]
            for k in stale:
                _dedup.pop(k, None)

        for owner_id in OWNER_ID:
            try:
                await app.send_message(owner_id, msg, parse_mode="html")
            except Exception:
                pass
    except Exception:
        # Never let notification failure break the bot
        pass


def notify_on_error(tag: str, context: str = ""):
    """Decorator that catches exceptions, notifies owner, then re-raises."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                try:
                    await notify_owner(tag, e, context)
                except Exception:
                    pass
                raise
        return wrapper
    return decorator
