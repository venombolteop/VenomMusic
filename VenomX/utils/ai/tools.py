# All rights reserved.
#
# Whitelisted AI tool actions.
#
# The model NEVER calls these directly. It only ever produces a JSON payload;
# the bot reads it, validates every field type/value, and only then runs one
# of the four approved actions below (search/queue songs, read history, read
# stats, write a fun-fact). Anything the model returns that is not exactly
# the documented shape is ignored. There is deliberately no exec, no eval,
# no shell, no file IO here - that is the whole point of this module.

import logging

_SEARCH_CAP = 10
_NAME_MAX = 80

_LOG = logging.getLogger("[VenomAI-tools]")


def _clean_names(payload) -> list:
    """Extract & validate a list of plain song names out of a model payload.

    Accepts a raw JSON string, {"songs": [..]} / {"names":[..]} / any
    dict key holding a list of titles, or a bare list. Every entry must be a
    plain string (numbers and objects are dropped) and is bounded.
    """
    if isinstance(payload, str):
        import ast as _ast
        import json as _json
        import re as _re

        m = _re.search(r"\{.*\}", payload, _re.DOTALL)
        blob = (m.group(0) if m else payload).strip()
        try:
            payload = _json.loads(blob)
        except Exception:  # noqa: BLE001
            try:
                # A python-repr dict (single quotes) from an upstream str()
                payload = _ast.literal_eval(blob)
            except Exception:  # noqa: BLE001
                payload = None
    names = None
    if isinstance(payload, str) and payload.strip():
        names = [payload]
    elif isinstance(payload, dict):
        for key in ("songs", "song", "names", "titles", "tracks", "queue",
                    "playlist", "query", "result", "results"):
            val = payload.get(key)
            if isinstance(val, list) and val:
                names = val
                break
            if isinstance(val, str) and val.strip():
                names = [val]
                break
        if names is None:
            # The model drifts key names ("queue", "party", ...). Any value
            # that is a list of plain strings is good enough.
            fallback = [
                val for val in payload.values()
                if isinstance(val, list) and any(
                    isinstance(x, (str, dict)) for x in val
                )
            ]
            if fallback:
                names = fallback[0]
            else:
                strings = [
                    val for val in payload.values()
                    if isinstance(val, str) and val.strip()
                ]
                if strings and len(strings) <= len(payload):
                    names = [strings[0]]
    elif isinstance(payload, list):
        names = payload
    if not names:
        return []
    out = []
    for item in names[:_SEARCH_CAP]:
        if isinstance(item, str) and item.strip():
            out.append(item.strip()[:_NAME_MAX])
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            out.append(item["name"].strip()[:_NAME_MAX])
    return out


clean_names = _clean_names


async def resolve_ids(names: list) -> list:
    """Resolve plain song names to YouTube video ids (validated, capped).

    Uses the same search backend the /play command uses, so behaviour is
    identical for a human query and an AI DJ query.
    """
    ids, seen = [], set()
    if not names:
        return ids
    from VenomX import Platform

    for name in names[:_SEARCH_CAP]:
        try:
            details, track_id = await Platform.youtube.track(name)
            if track_id and track_id not in seen:
                seen.add(track_id)
                ids.append({"id": track_id, "details": details})
        except Exception as e:
            _LOG.warning(f"resolve failed for {name[:40]!r}: {type(e).__name__}")
    return ids


def _facts_prompt(title: str) -> tuple:
    sys = (
        "ONE fun fact about this song/artist for a music bot's play card. "
        "Max 12 words, Hinglish, spicy but clean. Reply with ONLY the fact "
        "sentence, nothing else."
    )
    user = safety_shielded(title)
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]


def safety_shielded(text: str) -> str:
    from .safety import cap_input, shield

    return shield(cap_input(text))


async def fun_fact(title: str) -> str | None:
    """Cached (one AI call per unique song title, ever) Hinglish one-liner."""
    from . import memory as mem
    from .brain import chat

    title = safety_shielded(title)[: _NAME_MAX]
    cached = await mem.get_fact(title)
    if cached:
        return cached
    if not title:
        return None
    try:
        text, _ = await chat(_facts_prompt(title))
        text = str(text).strip().splitlines()[-1].strip()[:300] if text else ""
    except Exception as e:
        _LOG.warning(f"fun_fact failed: {type(e).__name__}")
        return None
    await mem.save_fact(title, text)
    return text
