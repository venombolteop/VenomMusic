# VenomX rich message helper — Bot API 10.3 rich messages, all MTProto.
#
# Everything goes through the bot's pyroblack client: send_rich_message,
# messages.EditMessage with rich_message, delete_messages. Native MTProto
# edits keep premium-emoji document entities alive (the HTTP Bot API strips
# them back to plain emoji on edit); callback updates still arrive through
# the client's normal handlers.

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import httpx

from VenomX.utils.premium import _DB_EMOJI_FALLBACK

import logging

log = logging.getLogger(__name__)

_EMOJI_DB_PATH = Path(
    os.environ.get(
        "PREMIUM_EMOJI_DB",
        os.path.join(os.path.dirname(__file__), "smart_emoji_db.json"),
    )
)
try:
    _EMOJI_DB = json.loads(_EMOJI_DB_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    # Same graceful degradation as premium.load_db(): panels fall back to
    # plain unicode emojis when the premium emoji database is not installed.
    _EMOJI_DB = {}

# Emojis used across the panels that are missing from the DB, mapped to
# verified equivalents whose ids ARE in the DB (play/pause/stop/nav icons).
_RICH_EMOJI_FALLBACK = _DB_EMOJI_FALLBACK


def pemoji(em: str) -> str:
    """Wrap an emoji in a premium custom emoji tag when the DB has one."""
    cid = pick_id(em)
    if not cid:
        return em
    return f'<tg-emoji emoji-id="{cid}">{em}</tg-emoji>'


_CHOSEN: dict = {}


def pick_id(em: str) -> str | None:
    key = em.replace("\ufe0f", "")
    if key in _CHOSEN:
        return _CHOSEN[key]
    ids = (_EMOJI_DB.get(key) or {}).get("ids") or []
    cid = None
    if ids:
        cid = ids[0]
    else:
        fb = _RICH_EMOJI_FALLBACK.get(key)
        if fb:
            ids = (_EMOJI_DB.get(fb) or {}).get("ids") or []
            if ids:
                cid = ids[0]
    _CHOSEN[key] = cid
    return cid


def rich_esc(text: str) -> str:
    """HTML-escape text but keep the tags rich messages understand.

    Mentions arrive as full <a href="tg://user?id=…">…</a> fragments inside
    lang strings and user names; escaping those wholesale broke links and
    showed raw markup, so safe tags pass through untouched.
    """
    raw = str(text)
    out = []
    last = 0
    for m in _TAG_KEEP_RE.finditer(raw):
        out.append(str(raw[last:m.start()]).replace("&", "&amp;")
                   .replace("<", "&lt;").replace(">", "&gt;"))
        tag = m.group(0)
        out.append(not_hm(tag))
        last = m.end()
    out.append(str(raw[last:]).replace("&", "&amp;")
               .replace("<", "&lt;").replace(">", "&gt;"))
    return "".join(out)


def not_hm(tag: str) -> str:
    """Normalise one allowed tag: quote bare href values."""
    fixed = re.sub(r'href=([^"\' >][^ >]*)', r'href="\1"', tag)
    return fixed


def rich_user_link(user) -> str:
    """A render-safe user reference for rich messages and queue tags.

    Telegram's pyrogram mention is an <a href="tg://user…"> fragment, which
    rich-message rendering strips — the raw tag leaks as text on the
    now-playing card. Names must link to the t.me profile instead, or
    stay plain text when the user has no username.
    """
    try:
        name = rich_esc(user.first_name or "ᴜɴᴋɴᴏᴡɴ")
        username = getattr(user, "username", None)
        if username:
            return f'<a href="https://t.me/{rich_esc(username)}">{name}</a>'
        return name
    except Exception:
        return "ᴜɴᴋɴᴏᴡɴ"


def rich_heading(text: str, level: int = 4) -> str:
    return f"<h{level}>{text}</h{level}>"


def rich_img(url: str) -> str:
    return f'<img src="{url}"/>'


def rich_button(text: str, callback_data: str = "", style: str = "primary") -> str:
    return (
        f'<tg-button type="callback_data" style="{style}" '
        f'data="{callback_data}">{text}</tg-button>'
    )


def rich_url_button(text: str, url: str, style: str = "primary") -> str:
    return f'<tg-button type="url" style="{style}" url="{url}">{text}</tg-button>'


def rich_switch_button(text: str, query: str, style: str = "primary") -> str:
    return (
        f'<tg-button type="switch_inline_query_current_chat" style="{style}" '
        f'query="{query}">{text}</tg-button>'
    )


def rich_button_row(*buttons: str, align: str = "") -> str:
    """Row of rich buttons; optional align: left / center / right."""
    open_attr = f' align="{align}"' if align else ""
    return f"<tg-button-row{open_attr}>" + "".join(buttons) + "</tg-button-row>"


def rich_note(text: str) -> str:
    """Block-quoted note block — draws attention like a callout card."""
    return f"<blockquote>{text}</blockquote>"


def rich_kv(label: str, value) -> str:
    """One 'key: value' line with a highlighted value."""
    return f"{str(label)} <mark>{str(value)}</mark>"


def _ctl(emoji: str, label: str, callback: str, style: str, default_label: str = "") -> str:
    text = label or default_label
    return rich_button(f"{pemoji(emoji)} {text}", callback_data=callback, style=style)


def btn_play(label: str, callback: str) -> str:
    return _ctl("▶", label, callback, "success", "ᴘʟᴀʏ")


def btn_pause(label: str, callback: str) -> str:
    return _ctl("⏸", label, callback, "primary", "ᴘᴀᴜsᴇ")


def btn_skip(label: str, callback: str) -> str:
    return _ctl("⏩", label, callback, "primary", "sᴋɪᴘ")


def btn_stop(label: str, callback: str) -> str:
    return _ctl("🛑", label, callback, "danger", "sᴛᴏᴘ")


def btn_close(label: str, callback: str = "close") -> str:
    return _ctl("❌", label, callback, "danger", "ᴄʟᴏsᴇ")


def btn_back(label: str, callback: str) -> str:
    return _ctl("🚀", label, callback, "primary", "ʙᴀᴄᴋ")


def btn_loop(label: str, callback: str) -> str:
    return _ctl("🔁", label, callback, "primary", "ʟᴏᴏᴘ")


def btn_seek(label: str, callback: str) -> str:
    return _ctl("🎚", label, callback, "primary")


def btn_on(label: str, callback: str) -> str:
    return _ctl("✅", label, callback, "success")


def btn_off(label: str, callback: str) -> str:
    return _ctl("❌", label, callback, "danger")


# One httpx client, but only for non-Telegram HEAD checks (cover URLs).
_IMG_HTTP = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(max_keepalive_connections=8),
)


async def send_audio(chat_id: int, filepath: str, caption: str = "",
                     thumb: str | None = None, title: str = "",
                     performer: str = "", duration: int = 0):
    """Upload a song file via the pyroblack client; returns the Message."""
    return await _client().send_audio(
        chat_id=chat_id,
        audio=filepath,
        caption=caption,
        title=title or None,
        performer=performer or None,
        duration=duration or 0,
        thumb=thumb,
    )


async def send_video(chat_id: int, filepath: str, caption: str = "",
                     duration: int = 0, width: int = 0, height: int = 0,
                     thumb: str | None = None, streaming: bool = True):
    """Upload a video file via the pyroblack client; returns the Message."""
    return await _client().send_video(
        chat_id=chat_id,
        video=filepath,
        caption=caption,
        duration=duration or 0,
        width=width or 0,
        height=height or 0,
        supports_streaming=streaming,
        thumb=thumb,
    )



_TAG_KEEP_RE = re.compile(
    r"(<a\s+(?:href\s*=\s*(?:\"|')?[^ >]*(?:\"|')?)?[^>]*>"
    r"|</a>|<b>|</b>|<i>|</i>|<u>|</u>|<s>|</s>|<em>|</em>|<strong>|</strong>"
    r"|<code>|</code>|<pre(?:\s[^>]*)?>|</pre>|<br\s*/?>"
    r"|<blockquote>|</blockquote>|<tg-emoji[^>]*>|</tg-emoji>)"
)

def rich_md(text: str) -> str:
    """Escape markdown-ish help text and convert **bold** / `code` to HTML."""
    esc = rich_esc(text)
    esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc, flags=re.DOTALL)
    esc = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", esc)
    return esc


_EMOJI_SORTED = sorted((_EMOJI_DB.keys()), key=len, reverse=True)
_EMOJI_RE = re.compile(
    "(" + "|".join(re.escape(k) for k in _EMOJI_SORTED if len(k) >= 2) + ")"
)
_EMOJI_SINGLE_RE = re.compile(
    "(" + "|".join(re.escape(k) for k in _EMOJI_SORTED if len(k) == 1) + ")"
)


_CODE_SEG_RE = re.compile(r"(<pre\b.*?</pre>|<code\b.*?</code>)", re.DOTALL)
_P_SEG_RE = re.compile(r"(<p\b[^>]*>.*?</p>)", re.DOTALL)


def _protect_code(html: str):
    """Swap <code>/<pre> blocks for placeholders so passes can skip them."""
    stash = []

    def _keep(m):
        stash.append(m.group(0))
        return f"\x00CODE{len(stash) - 1}\x00"

    return _CODE_SEG_RE.sub(_keep, html), stash


def _restore_code(html: str, stash) -> str:
    for i, block in enumerate(stash):
        html = html.replace(f"\x00CODE{i}\x00", block)
    return html


def _nl_fix(html: str) -> str:
    """Rich paragraphs collapse newlines, so split them into real <p> blocks.

    Line breaks inside <p>…</p> become </p><p> boundaries; <code>/<pre> blocks
    (inline or standalone) keep their internal newlines.
    """
    html, stash = _protect_code(html)
    out = []
    for seg in _P_SEG_RE.split(html):
        if seg.startswith("<p"):
            seg = re.sub(r"\n", "</p><p>", seg)
            seg = seg.replace("<p></p>", "")
        out.append(seg)
    return _restore_code("".join(out), stash)


def _protect_custom_emojis(html: str):
    """Keep existing custom-emoji entities intact during visible-text emoji conversion."""
    stash = []

    def _keep(m):
        stash.append(m.group(0))
        return f"\x00EMOJI{len(stash) - 1}\x00"

    protected = re.sub(
        r"(<tg-emoji\b[^>]*>.*?</tg-emoji>"
        r"|<img\s+src=\"tg://emoji\?id=\d+\"[^>]*/?>)",
        _keep, html, flags=re.DOTALL)
    return protected, stash


def _restore_custom_emojis(html: str, stash) -> str:
    for i, tag in enumerate(stash):
        html = html.replace(f"\x00EMOJI{i}\x00", tag)
    return html


def _beautify(html: str) -> str:
    """Post-process: leftover **bold**, `code`, and premium-emoji pass.

    Every emoji char that has a DB id anywhere in visible text is upgraded to
    its premium custom-emoji tag, so panels never ship plain emoji.
    """
    html, emoji_stash = _protect_custom_emojis(html)
    html, stash = _protect_code(html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html, flags=re.DOTALL)
    html = re.sub(r"__(.+?)__", r"<i>\1</i>", html, flags=re.DOTALL)
    html = re.sub(r"--(.+?)--", r"<u>\1</u>", html, flags=re.DOTALL)
    html = re.sub(r"~~(.+?)~~", r"<s>\1</s>", html, flags=re.DOTALL)
    html = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", html)
    html = _restore_code(html, stash)

    def _swap(m):
        cid = pick_id(m.group(0))
        if not cid:
            return m.group(0)
        return f'<tg-emoji emoji-id="{cid}">{m.group(0)}</tg-emoji>'

    # Replace emoji only in visible text, never inside HTML tags/attributes.
    # Splitting around tags also preserves any existing <img src="tg://emoji..."/>.
    parts = re.split(r"(<[^>]*>)", html)
    for i in range(0, len(parts), 2):
        parts[i] = _EMOJI_RE.sub(_swap, parts[i])
        parts[i] = _EMOJI_SINGLE_RE.sub(_swap, parts[i])
    html = "".join(parts)
    html = _restore_custom_emojis(html, emoji_stash)
    return _nl_fix(html)


async def url_ok(url: str) -> bool:
    """HEAD-check an image URL (best effort — assumes yes on any failure)."""
    try:
        resp = await _IMG_HTTP.head(url)
        return resp.status_code == 200
    except Exception:
        return True


def md_to_rich(md: str) -> str:
    """Model markdown into rich-HTML blocks (headings/lists/code/quotes).

    The plugins that show free-form model output call this instead of wrapping
    everything in <p>, so the reply renders with Telegram's native Structures
    instead of one flat paragraph.
    """
    lines = md.splitlines()
    out: list[str] = []
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append("<p>" + "<br>".join(rich_esc(x) for x in para) + "</p>")
            para.clear()

    i = 0
    in_code = False
    code: list[str] = []
    lang = ""
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("```"):
            if in_code:
                body = rich_esc("\n".join(code))
                out.append(f"<pre><code class=\"language-{rich_esc(lang)}\">{body}</code></pre>" if lang else f"<pre>{body}</pre>")
                code, lang = [], ""
                in_code = False
            else:
                in_code = True
                lang = s[3:].strip()
            i += 1
            continue
        if in_code:
            code.append(lines[i])
            i += 1
            continue
        if not s:
            flush_para()
            i += 1
            continue
        if s in ("---", "***", "___"):
            flush_para()
            out.append("<hr/>")
            i += 1
            continue
        hash_n = len(s) - len(s.lstrip("#"))
        if 1 <= hash_n <= 6 and s[hash_n:hash_n + 1] == " ":
            flush_para()
            out.append(f"<h4>{rich_esc(s[hash_n + 1:].strip())}</h4>")
            i += 1
            continue
        if s.startswith(("- ", "* ", "• ")):
            flush_para()
            items: list[str] = []
            while i < len(lines):
                t = lines[i].strip()
                if t.startswith(("- ", "* ", "• ")):
                    items.append(t[2:])
                    i += 1
                else:
                    break
            out.append("<ul>" + "".join(f"<li>{rich_esc(x)}</li>" for x in items) + "</ul>")
            continue
        numbered = re.match(r"^(\d+)[.)]\s+(.*)$", s)
        if numbered:
            flush_para()
            items2: list[str] = []
            while i < len(lines):
                m2 = re.match(r"^(\d+)[.)]\s+(.*)$", lines[i].strip())
                if m2:
                    items2.append(m2.group(2))
                    i += 1
                else:
                    break
            out.append("<ol>" + "".join(f"<li>{rich_esc(x)}</li>" for x in items2) + "</ol>")
            continue
        if s.startswith(">"):
            flush_para()
            buf = [s[1:].strip()]
            while i + 1 < len(lines) and lines[i + 1].strip().startswith(">"):
                i += 1
                buf.append(lines[i].strip()[1:].strip())
            out.append("<blockquote>" + rich_esc(" ".join(x for x in buf if x)) + "</blockquote>")
            i += 1
            continue
        para.append(lines[i])
        i += 1
    flush_para()
    return "\n".join(out)


def _client():
    """The bot's MTProto client, once pyroblack rich methods are the path."""
    from VenomX import app as app_client

    return app_client


def _mid_from_updates(exc):
    """Message id out of the raw Updates that pyroblack failed to parse."""
    tb = exc.__traceback__
    r = None
    while tb is not None:
        if tb.tb_frame.f_code.co_name == "send_rich_message":
            r = tb.tb_frame.f_locals.get("r")
        tb = tb.tb_next
    if r is None:
        return None
    mid = getattr(r, "id", None)
    if isinstance(mid, int):
        return mid
    ups = getattr(r, "updates", None)
    if ups is not None and not isinstance(ups, (list, tuple)):
        ups = getattr(ups, "updates", None) or []
    for u in ups or []:
        mid = getattr(getattr(u, "message", None), "id", None)
        if isinstance(mid, int):
            return mid
        # Bot sendMessage replies carry Updates(updateMessageID): the id
        # sits directly on the UpdateMessageID entry, no message payload.
        mid = getattr(u, "id", None)
        if isinstance(mid, int):
            return mid
    return None


async def send_rich(chat_id: int, html: str, reply_markup=None) -> int | None:
    """Send a rich message via the inbuilt pyroblack method."""
    from pyrogram.errors import RPCError
    from pyrogram.types import InputRichMessage

    try:
        kwargs = {}
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        msg = await _client().send_rich_message(
            chat_id, InputRichMessage(html=_beautify(html)), **kwargs
        )
        return int(msg.id)
    except AttributeError as e:
        # pyroblack bot bug: raw Updates parses fine over MTProto but its
        # utils.parse_messages expects .messages — the message IS sent, so
        # recover the id from the raw payload instead of re-sending (dupe).
        _mid = _mid_from_updates(e)
        if _mid:
            return _mid
        log.warning(
            "send_rich_message sent but raw id not recoverable (%s)",
            type(e).__name__,
        )
        return None
    except Exception:
        log.warning("send_rich_message failed", exc_info=True)
        return None


async def edit_rich(chat_id: int, message_id: int, html: str, reply_markup=None) -> bool:
    """Edit a rich message through the pyroblack client.

    Native MTProto edits keep the premium-emoji document entities intact —
    the HTTP Bot API strips them back to plain emoji in groups.
    """
    from pyrogram.errors import MessageNotModified
    from pyrogram.raw import functions as raw_functions
    from pyrogram.types import InputRichMessage

    try:
        c = _client()
        rpc = raw_functions.messages.EditMessage(
            peer=await c.resolve_peer(chat_id),
            id=int(message_id),
            rich_message=InputRichMessage(html=_beautify(html)).write(),
            reply_markup=await reply_markup.write(c) if reply_markup else None,
        )
        await c.invoke(rpc)
        return True
    except MessageNotModified:
        return True
    except Exception:
        log.warning("rich edit failed in %s", chat_id, exc_info=True)
        return False


async def send_rich_draft(chat_id: int, draft_id: int, html: str) -> bool:
    """Stream a partial rich message (30-second preview) while generating."""
    from pyrogram.types import InputRichMessage

    try:
        await _client().send_rich_message_draft(
            chat_id, int(draft_id), InputRichMessage(html=_beautify(html))
        )
        return True
    except Exception:
        log.debug("draft stream skipped", exc_info=True)
        return False


async def ai_stream(chat_id: int, chat_id_int: int, chunk_html: str) -> None:
    """Convenience wrapper the AI lane calls with progressive HTML."""
    await send_rich_draft(chat_id, chat_id_int, chunk_html)


async def edit_reply_markup(chat_id: int, message_id: int, reply_markup) -> bool:
    """Edit only the inline keyboard via the client (keeps emoji icons)."""
    from pyrogram.raw import functions as raw_functions

    try:
        c = _client()
        await c.invoke(
            raw_functions.messages.EditMessage(
                peer=await c.resolve_peer(chat_id),
                id=int(message_id),
                reply_markup=await reply_markup.write(c),
            )
        )
        return True
    except Exception:
        log.warning("reply-markup edit failed in %s", chat_id, exc_info=True)
        return False


async def delete_msg(chat_id: int, message_id: int) -> bool:
    try:
        await _client().delete_messages(chat_id, [int(message_id)])
        return True
    except Exception:
        log.warning("delete failed in %s for %s", chat_id, message_id, exc_info=True)
        return False


class RichMystic:
    """Drop-in status-message adapter for code that expects a pyrogram Message.

    edit_text/delete/reply_text map onto the MTProto rich-message helpers,
    so stream()/helpers can drive a rich card instead of a plain bubble.
    """

    def __init__(self, chat_id: int, message_id: int):
        self.chat_id = chat_id
        self.id = message_id

    async def edit_text(self, text: str, reply_markup=None, **kw) -> bool:
        if not self.id:
            return False
        html = f"<p>{rich_esc(text)}</p>"
        return await edit_rich(self.chat_id, self.id, html)

    async def edit(self, text: str, reply_markup=None, **kw) -> bool:
        return await self.edit_text(text)

    async def reply_text(self, text: str, reply_markup=None, **kw) -> "RichMystic":
        mid = await send_rich(
            self.chat_id, f"<p>{rich_esc(text)}</p>"
        )
        return RichMystic(self.chat_id, mid) if mid else self

    async def delete(self, **kw) -> bool:
        if not self.id:
            return False
        return await delete_msg(self.chat_id, self.id)


async def status_card(chat_id: int, text: str, fallback_message=None):
    """Send a rich 'working on it...' card and return its adapter handle.

    fallback_message: a pyrogram Message used verbatim (reply) when the rich
    send fails, so the status stays visible instead of silently no-oping.
    """
    mid = await send_rich(chat_id, f"<p>{rich_esc(text)}</p>")
    if not mid and fallback_message is not None:
        try:
            return await fallback_message.reply_text(
                text, disable_web_page_preview=True
            )
        except Exception:  # noqa: BLE001
            return RichMystic(chat_id, None)
    return RichMystic(chat_id, mid)


def ids_of(m) -> tuple[int | None, int | None]:
    """(chat_id, message_id) for a RichMystic or a pyrogram Message."""
    chat_id = getattr(m, "chat_id", None)
    if chat_id is None:
        chat_id = getattr(getattr(m, "chat", None), "id", None)
    return chat_id, getattr(m, "id", None)


async def send_note(chat_id: int, text: str, heading: str | None = None,
                    style: str = "primary") -> int | None:
    """One-off rich notice card (admin actions, statuses, log lines).

    Callout-blockquote body so the note pops against chat background, and a
    single centered close row.
    """
    body = ""
    if heading:
        body += rich_heading(f"{pemoji('🎵')} {rich_esc(heading)}", level=4)
    body += rich_note(rich_esc(text).replace("\n", "<br>"))
    body += rich_button_row(
        rich_button(f"{pemoji('❌')} ᴄʟᴏsᴇ", callback_data="close", style="danger",
                    ),
        align="center",
    )
    return await send_rich(chat_id, body)


async def edit_any(mystic, text: str, reply_markup=None) -> bool:
    """Rich-edit a message; pyrogram edit_text is the failure fallback.

    Accepts a RichMystic or a pyrogram Message so every edit site can stay
    row-blind: first try the rich edit, then the classic edit.
    """
    chat_id, mid = ids_of(mystic)
    if chat_id and mid:
        try:
            if await edit_rich(chat_id, mid, f"<p>{rich_esc(text)}</p>"):
                return True
        except Exception:  # noqa: BLE001
            pass
    try:
        await mystic.edit_text(text, reply_markup=reply_markup,
                               disable_web_page_preview=True)
        return True
    except Exception:  # noqa: BLE001
        return False


async def reply_note(message, text: str, **kw) -> int | None:
    """Reply to a command with a rich notice card; plain reply is the fallback."""
    try:
        mid = await send_rich(message.chat.id, f"<p>{rich_esc(text)}</p>")
        if not mid and kw.get("reply_markup") is not None:
            await message.reply_text(text, **kw)
        return mid
    except Exception:  # noqa: BLE001
        try:
            await message.reply_text(text, **kw)
        except Exception:  # noqa: BLE001
            pass
        return None


async def reply_rich(message, text: str, reply_markup=None) -> int | None:
    """Reply with a rich card; returns the new message id (or None)."""
    try:
        return await send_rich(message.chat.id, f"<p>{rich_esc(text)}</p>",
                               reply_markup=reply_markup)
    except Exception:  # noqa: BLE001
        return None


