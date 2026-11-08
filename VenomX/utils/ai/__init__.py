# All rights reserved.
#
# Venom AI package: brain + safety + memory + tools + voice.
# Plugins go through ``enabled()`` first.

from config import config

_VALID = ("auto", "local", "cloud")


async def enabled() -> tuple:
    """(is_on, reason_code). Respects .env provider config + Mongo kill switch."""
    if config.AI_PROVIDER not in _VALID:
        return False, "!provider"
    from . import memory as mem

    flag = await mem.get_setting(0, "ai_on", None)
    if flag is False:
        return False, "!killed"
    return True, ""
