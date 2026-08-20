
# All rights reserved.

# Premium emoji + colored button support.
#
# Loads the premium emoji database (smart_emoji_db.json) which maps unicode
# emojis to their premium (custom) emoji document ids. Emojis that are not
# available in the database are swapped with the closest available equivalent
# so every emoji the bot uses can be rendered as a premium (animated) emoji.

import json
import os
import random

from pyrogram.enums import ButtonStyle
from pyrogram.raw import types as raw_types
from pyrogram.types import InlineKeyboardButton

EMOJI_DB_PATH = os.environ.get(
    "PREMIUM_EMOJI_DB",
    os.path.join(os.path.dirname(__file__), "smart_emoji_db.json")
    if os.path.exists(os.path.join(os.path.dirname(__file__), "smart_emoji_db.json"))
    else "/home/ubuntu/wel/smart_emoji_db.json"
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
    """Pick a random premium custom emoji id for an emoji, or None.

    Random every call so each message/button render looks unique.
    """
    ids = emoji_ids(emoji)
    if not ids:
        # Try fallback unicode equivalent that exists in the DB
        fb = _EMOJI_FALLBACK.get(_norm(emoji)) or _EMOJI_FALLBACK.get(emoji)
        if fb:
            ids = emoji_ids(fb)
    if not ids:
        return None
    return random.choice(ids)


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


# ══════════════════════════════════════════════════════════════════════════════
# Premium button factories — NO DEFAULT/GRAY anywhere
# ══════════════════════════════════════════════════════════════════════════════

def _strip_emojis(text):
    """Remove all emoji characters from text — premium icon replaces them.
    Preserves progress bar chars (▰▱) and block elements used for UI."""
    if not text:
        return text
    out = []
    for c in text:
        cp = ord(c)
        if (
            0x1F000 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x27BF
            or 0x2B00 <= cp <= 0x2BFF
            or cp == 0x200D
            or 0xFE00 <= cp <= 0xFE0F
            or cp == 0x20E3
            or 0x2190 <= cp <= 0x21FF
            or 0x2300 <= cp <= 0x23FF
            or (0x25AA <= cp <= 0x25FE and cp not in (0x25B0, 0x25B1, 0x25AC, 0x25AD, 0x25AE, 0x25AF))
            or 0x2934 <= cp <= 0x2935
            or 0x3030 <= cp <= 0x303D
            or cp in (0x2122, 0x2139, 0x21A9, 0x21AA, 0x2328, 0x23CF,
                       0x23E9, 0x23EA, 0x23EB, 0x23EC, 0x23ED, 0x23EE,
                       0x23EF, 0x23F0, 0x23F1, 0x23F2, 0x23F3, 0x23F8,
                       0x23F9, 0x23FA, 0x25FB, 0x25FC, 0x25FD, 0x25FE,
                       0x2614, 0x2615, 0x2648, 0x2649, 0x264A, 0x264B,
                       0x264C, 0x264D, 0x264E, 0x264F, 0x2650, 0x2651,
                       0x2652, 0x2653, 0x267F, 0x2693, 0x26A1, 0x26AA,
                       0x26AB, 0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26CE,
                       0x26D4, 0x26EA, 0x26F2, 0x26F3, 0x26F5, 0x26FA,
                       0x26FD, 0x2702, 0x2705, 0x2708, 0x2709, 0x270A,
                       0x270B, 0x270C, 0x270F, 0x2712, 0x2714, 0x2716,
                       0x271D, 0x2721, 0x2728, 0x2733, 0x2734, 0x2744,
                       0x2747, 0x274C, 0x274E, 0x2753, 0x2754, 0x2755,
                       0x2757, 0x2763, 0x2764, 0x2795, 0x2796, 0x2797,
                       0x27A1, 0x27B0, 0x27BF, 0x2934, 0x2935, 0x2B05,
                       0x2B06, 0x2B07, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55,
                       0x303D, 0x3297, 0x3299)
        ):
            continue
        out.append(c)
    return "".join(out)


# Fallback emoji for button factories — maps missing DB emojis to ones that exist
_BTN_EMOJI_FALLBACK = {
    "\U0001f504": "\u2b50",   # 🔄 → ⭐
    "\U0001f4f1": "\U0001f3b6",  # 📱 → 🎶
    "\u2728": "\u2b50",       # ✨ → ⭐
    "\U0001f4bb": "\U0001f525",  # 💻 → 🔥
    "\u25b6": "\u2b50",       # ▶ → ⭐
    "\u23e9": "\u23ed",       # ⏩ → ⏭
    "\U0001f535": "\u2b50",   # 🔵 → ⭐
    "\U0001f6d1": "\u274c",   # 🛑 → ❌
    "\U0001f501": "\u2b50",   # 🔁 → ⭐
    "\U0001f500": "\u2b50",   # 🔀 → ⭐
    "\U0001f3a8": "\U0001f3b6",  # 🎨 → 🎶
    "\U0001f3ac": "\U0001f3b5",  # 🎬 → 🎵
    "\U0001f4f7": "\U0001f4f1",  # 📷 → 📱 (might fail too, chain)
    "\U0001f4e2": "\U0001f3a4",  # 📢 → 🎤
    "\U0001f4ca": "\U0001f4cb",  # 📊 → 📋
    "\U0001f5bc": "\U0001f4f7",  # 🖼 → 📷
}


def _resolve_btn_emoji(emoji):
    """Try pick_id, then fallback, then skip."""
    eid = pick_id(emoji)
    if eid:
        return eid
    fb = _BTN_EMOJI_FALLBACK.get(emoji)
    if fb:
        eid = pick_id(fb)
        if eid:
            return eid
    return None


def _btn(text, callback_data=None, url=None, style=ButtonStyle.PRIMARY, emoji=None):
    """Core button builder — never uses DEFAULT style.
    When emoji is set, strips all emoji chars from text (premium icon replaces them).
    Falls back to alternative emojis if the requested one is missing from DB."""
    clean_text = _strip_emojis(text) if emoji else text
    kw = dict(text=clean_text, style=style)
    if emoji:
        eid = _resolve_btn_emoji(emoji)
        if eid:
            kw["icon_custom_emoji_id"] = eid
    if url:
        kw["url"] = url
    elif callback_data:
        kw["callback_data"] = callback_data
    return InlineKeyboardButton(**kw)


def play_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="▶")


def pause_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⏸")


def skip_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⏩")


def stop_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="🛑")


def close_btn(text, callback_data="close"):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="❌")


def back_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔄")


def nav_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔵")


def on_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="✅")


def off_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="🚫")


def music_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🎵")


def video_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🎬")


def star_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⭐")


def settings_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⚙️")


def loop_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔁")


def shuffle_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔀")


def mute_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔇")


def unmute_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="🔊")


def seek_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⏱")


def replay_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔁")


def fire_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔥")


def spark_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="✨")


def warn_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="🟠")


def phone_btn(text, callback_data=None, url=None):
    return _btn(text, callback_data=callback_data, url=url, style=ButtonStyle.PRIMARY, emoji="📱")


def link_btn(text, url, emoji=None):
    return _btn(text, url=url, style=ButtonStyle.PRIMARY, emoji=emoji)


def custom_btn(text, callback_data=None, url=None, style=ButtonStyle.PRIMARY, emoji=None):
    """Generic button with explicit style + optional emoji."""
    return _btn(text, callback_data=callback_data, url=url, style=style, emoji=emoji)


# --- Additional button factories ---

def volume_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔊")


def queue_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="📋")


def download_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="📥")


def refresh_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔄")


def info_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="ℹ️")


def search_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔍")


def like_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="❤️")


def share_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="📤")


def bookmark_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔖")


def next_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⏩")


def prev_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⏪")


def help_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="❓")


def pin_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="📌")


def clear_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="🧹")


def mic_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🎤")


def headphone_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🎧")


def eq_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🎛")


def timer_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⏰")


def rocket_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="🚀")


def lock_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="🔐")


def globe_btn(text, url, emoji="🌐"):
    return _btn(text, url=url, style=ButtonStyle.PRIMARY, emoji=emoji)


def check_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="☑️")


def cross_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="✖️")


def lightning_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="⚡")


def shield_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🛡")


def heart_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.DANGER, emoji="💖")


def music2_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.SUCCESS, emoji="🎵")


def speaker_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="🔉")


def rewind_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⏪")


def fastfwd_btn(text, callback_data):
    return _btn(text, callback_data=callback_data, style=ButtonStyle.PRIMARY, emoji="⏩")
