
# All rights reserved.

# Premium emoji + colored button support.
#
# Loads the premium emoji database (smart_emoji_db.json) which maps unicode
# emojis to their premium (custom) emoji document ids. Emojis that are not
# available in the database are swapped with the closest available equivalent
# so every emoji the bot uses can be rendered as a premium (animated) emoji.

import json
import os

from pyrogram.raw import types as raw_types

EMOJI_DB_PATH = os.environ.get(
    "PREMIUM_EMOJI_DB", "/home/ubuntu/wel/smart_emoji_db.json"
)

_emoji_db = None

# Emojis not present in the premium database mapped to the closest available
# equivalent that IS present in the database.
_EMOJI_FALLBACK = {
    "🆓": "🆗",
    "🌋": "🔥",
    "🌸": "🌺",
    "🏘": "🏡",
    "🏮": "🎊",
    "👤": "🧑",
    "👥": "👬",
    "👨‍⚖": "⚖",
    "💕": "💖",
    "💡": "✨",
    "📃": "📋",
    "📍": "📌",
    "📜": "📖",
    "📡": "📶",
    "📢": "🔊",
    "🔍": "🔎",
    "🔑": "🔐",
    "🔒": "🔐",
    "🔓": "🔐",
    "🔖": "🏷",
    "🔗": "🌐",
    "🔙": "🔄",
    "🔢": "🔤",
    "🕕": "🕰",
    "🕜": "🕰",
    "🗒": "📝",
    "🗣": "🔊",
    "🙄": "🙃",
    "🙍": "🙁",
    "🚫": "⛔",
    "🥀": "🌹",
    "🥱": "😴",
    "🦸": "🤴",
    "🧑‍💻": "💻",
    "🧑‍🚀": "🚀",
    "🧛": "👻",
    "🧺": "🛒",
    "🪄": "✨",
    "✚": "➕",
    "⏳": "⏰",
    "⏹": "🛑",
    "🔇": "🔕",
    "☀": "🌤",
    "❇": "✨",
    "❮": "👈",
    "❯": "👉",
    "↻": "🔄",
    "↪": "🔄",
    "⇆": "🔁",
    "🏴": "🇬🇧",
    "🇦🇪": "🌐",
    "🇹🇷": "🌐",
    "⏮": "👈",
    "⏭": "👉",
    # decorative separators and stars -> sparkle
    "➻": "💫",
    "➛": "💫",
    "➲": "💫",
    "➤": "💫",
    "➥": "💫",
    "➣": "💫",
    "✭": "💫",
    "✮": "💫",
    "✯": "💫",
    "✬": "💫",
    "✧": "💫",
    "★": "💫",
}


def _norm(emoji):
    return emoji.replace("\ufe0f", "")


def _is_emoji_char(cp):
    return (
        0x1F000 <= cp <= 0x1FAFF
        or cp == 0x20E3
        or 0x2190 <= cp <= 0x27BF
        or 0x2B00 <= cp <= 0x2BFF
        or cp == 0x200D
        or 0xFE00 <= cp <= 0xFE0F
        or 0x1F3FB <= cp <= 0x1F3FF
    )


def load_db():
    """Load the premium emoji database (cached)."""
    global _emoji_db
    if _emoji_db is None:
        try:
            with open(EMOJI_DB_PATH, encoding="utf-8") as f:
                _emoji_db = json.load(f)
        except Exception:
            _emoji_db = {}
    return _emoji_db


def is_available(emoji):
    """Whether the given emoji has premium variants in the database."""
    return _norm(emoji) in load_db()


def emoji_ids(emoji):
    """Custom emoji document ids available for an emoji."""
    entry = load_db().get(_norm(emoji)) or {}
    ids = entry.get("ids") or []
    return [str(i) for i in ids if str(i).isdigit()]


def pick_id(emoji):
    """Pick a stable custom emoji id for an emoji, or None."""
    ids = emoji_ids(emoji)
    if not ids:
        return None
    # Deterministic pick so edits of the same message keep the same emoji.
    return ids[sum(ord(c) for c in _norm(emoji)) % len(ids)]


def _iter_emojis(text):
    i = 0
    n = len(text)
    while i < n:
        if _is_emoji_char(ord(text[i])):
            j = i + 1
            while j < n and _is_emoji_char(ord(text[j])):
                j += 1
            yield i, j, text[i:j]
            i = j
        else:
            i += 1


def _split_run(run):
    chunks = []
    cur = ""
    prev_zwj = False
    for c in run:
        cp = ord(c)
        if (
            cp == 0x200D
            or 0xFE00 <= cp <= 0xFE0F
            or 0x1F3FB <= cp <= 0x1F3FF
            or cp == 0x20E3
        ):
            cur += c
            prev_zwj = cp == 0x200D
        elif prev_zwj:
            cur += c
            prev_zwj = False
        else:
            if cur:
                chunks.append(cur)
            cur = c
            prev_zwj = False
    if cur:
        chunks.append(cur)
    return chunks


def _normalize_run(run):
    norm = _norm(run)
    db = load_db()
    if norm in db:
        return norm
    if norm in _EMOJI_FALLBACK:
        return _EMOJI_FALLBACK[norm]
    chunks = _split_run(run)
    if len(chunks) <= 1:
        return run
    return "".join(_normalize_run(chunk) for chunk in chunks)


def normalize_text(text):
    """Replace every emoji with a premium-database-available equivalent."""
    if not text:
        return text
    out = []
    i = 0
    for start, end, run in _iter_emojis(text):
        out.append(text[i:start])
        out.append(_normalize_run(run))
        i = end
    out.append(text[i:])
    return "".join(out)


def _utf16_len(text):
    """Length of the text in UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def premium_entities(text):
    """Custom emoji entities (raw) for the premium emojis inside the text.

    Telegram requires entity offsets and lengths in UTF-16 code units, not
    Python code points, so the emoji run positions are converted.
    """
    entities = []
    if not text:
        return entities
    db = load_db()
    for start, end, run in _iter_emojis(text):
        pos = _utf16_len(text[:start])
        for chunk in _split_run(run):
            length = _utf16_len(chunk)
            norm = _norm(chunk)
            if norm in db:
                custom_id = pick_id(norm)
                if custom_id:
                    entities.append(
                        raw_types.MessageEntityCustomEmoji(
                            offset=pos,
                            length=length,
                            document_id=int(custom_id),
                        )
                    )
            pos += length
    return entities


def install_text_entities_patch():
    """Inject premium custom-emoji entities into every parsed text/caption."""
    import pyrogram.utils

    if getattr(pyrogram.utils, "_venom_premium_patch", False):
        return
    original = pyrogram.utils.parse_text_entities

    async def patched(client, text, parse_mode, entities):
        result = await original(client, text, parse_mode, entities)
        try:
            message = result.get("message")
            if not message or not isinstance(message, str):
                return result
            extra = premium_entities(message)
            if not extra:
                return result
            merged = list(result.get("entities") or []) + extra
            merged.sort(key=lambda e: e.offset)
            result["entities"] = merged or None
        except Exception:
            pass
        return result

    pyrogram.utils.parse_text_entities = patched
    pyrogram.utils._venom_premium_patch = True


async def validate_db(client, batch_size=100):
    """Drop premium emoji ids that Telegram no longer recognizes."""
    global _emoji_db
    db = load_db()
    if not db:
        return
    try:
        from pyrogram.raw.functions.messages import GetCustomEmojiDocuments

        all_ids = []
        for entry in db.values():
            ids = entry.get("ids") or []
            all_ids.extend(int(i) for i in ids if str(i).isdigit())
        all_ids = list(dict.fromkeys(all_ids))

        valid_ids = set()
        for i in range(0, len(all_ids), batch_size):
            batch = all_ids[i : i + batch_size]
            try:
                res = await client.invoke(
                    GetCustomEmojiDocuments(document_id=batch)
                )
            except Exception:
                # Transient error - keep those ids rather than drop them.
                valid_ids.update(str(i) for i in batch)
                continue
            for doc in res or []:
                valid_ids.add(str(doc.id))
    except Exception:
        return
    if not valid_ids:
        return
    new_db = {}
    for emoji, entry in db.items():
        new_db[emoji] = dict(entry)
        new_db[emoji]["ids"] = [
            i for i in (entry.get("ids") or []) if str(i) in valid_ids
        ]
    _emoji_db = new_db
