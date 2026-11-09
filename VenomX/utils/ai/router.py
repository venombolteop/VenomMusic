# All rights reserved.
#
# Intent router for /ai — three-tier, fastest first:
#
#   1. threat guard: hack / phish / scam requests -> ("threat",) and the
#      caller answers with a canned refusal. No model is ever called.
#   2. deterministic fast paths: "play <x>", skip/stop/pause/resume — zero
#      latency, zero AI tokens, no misclassification possible.
#   3. Cactus Needle (26-45M tiny tool-calling model, ~150ms on this box)
#      for the ambiguous midground (suggestion vs chitchat). Falls back to
#      ("chat",) on any error so /ai keeps working without it.
from VenomX.utils.ai import safety

_LOG_NAME = "[VenomAI-router]"

import asyncio
import logging
import re

_PLAY_RE = re.compile(r"^\s*(?:play|laga|lagao|bajao|sunao|chalu)\s+(.+?)\s*$", re.I)
_CTRL_RE = re.compile(r"^\s*(?:skip|next)\b", re.I)
_STOP_RE = re.compile(r"^\s*stop\b", re.I)

_NEEDLE_SYSTEM = (
    "You route Venom music bot /ai messages to exactly one tool. "
    "Use play_song when the user names or clearly wants a song. Use "
    "song_suggestion when they ask for ideas/vibe. Use no_tool for all "
    "plain questions, praise, and anything not music playback."
)

_STATE = {"n": None, "lock": asyncio.Lock()}


def _get_needle():
    """Lazy shared Needle router (never crashes import if package missing)."""
    if _STATE["n"] is not None:
        return _STATE["n"]
    from needle.agent.tools import tool
    from needle import Needle

    @tool
    def play_song(query: str) -> str:
        """Queue and play a specific song by name or mood."""
        return "play"

    @tool
    def song_suggestion(vibe: str) -> str:
        """Suggest songs matching a vibe or mood."""
        return "suggest"

    @tool
    def no_tool() -> str:
        """Use for plain questions about topics or general chitchat."""
        return "chat"

    _STATE["n"] = Needle(
        tools=[play_song, song_suggestion, no_tool],
        system=_NEEDLE_SYSTEM,
        stateless=True,
        generation=2,
    )
    return _STATE["n"]


async def _needle_route(text: str) -> str:
    async with _STATE["lock"]:
        n = await asyncio.to_thread(_get_needle)
        result = await asyncio.to_thread(n.complete, text)
    calls = result.get("function_calls") or []
    if not calls:
        return "chat"
    name = str(calls[0].get("name") or "chat")
    if name == "play_song":
        return "play"
    if name == "song_suggestion":
        return "suggest"
    return "chat"


async def route(text: str) -> tuple:
    """Classify a raw /ai message -> (action, arg).

    actions: threat, play, skip, stop, suggest, chat
    """
    text = safety.cap_input(str(text or ""))
    if not text.strip() or safety.threat(text):
        return ("threat", "")
    lower = text.lower()
    if _CTRL_RE.match(lower) or "skip karo" in lower or "skip kar" in lower:
        return ("skip", "")
    if _STOP_RE.match(lower) or "stop karo" in lower:
        return ("stop", "")
    m = _PLAY_RE.match(lower)
    if m:
        return ("play", m.group(1).strip())
    try:
        action = await asyncio.wait_for(_needle_route(text), timeout=30)
        if action == "play":
            # Needle wants playback but gave no title — treat as suggestion.
            return ("suggest", "")
        return (action, "")
    except Exception as e:  # noqa: BLE001
        logging.getLogger(_LOG_NAME).warning(f"needle unavailable: {type(e).__name__}")
        return ("chat", "")
