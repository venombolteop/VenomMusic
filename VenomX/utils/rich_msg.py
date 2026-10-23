# VenomX rich message helper — Bot API 10.3 rich messages over pure HTTP.
#
# Sends rich messages (music panels with per-track covers, inline buttons,
# switch-inline queue views, progress bars) and edits/deletes them, while the
# pyrogram client keeps receiving callback_query updates for these buttons
# through its normal handlers.  No MTProto client is created here, so this
# never touches auth.ImportBotAuthorization and never trips FLOOD_WAIT.

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import httpx

from VenomX.utils.premium import _DB_EMOJI_FALLBACK

from config import BOT_TOKEN

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

_EMOJI_DB_PATH = Path("/home/ubuntu/wel/smart_emoji_db.json")
_EMOJI_DB = json.loads(_EMOJI_DB_PATH.read_text(encoding="utf-8"))

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


def rich_kv(label: str, value: str) -> str:
    """One 'key: value' line with a highlighted value."""
    return f"{rich_esc(label)} <mark>{rich_esc(value)}</mark>"


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


_HTTP = httpx.AsyncClient(
    timeout=httpx.Timeout(45.0),
    limits=httpx.Limits(max_keepalive_connections=8),
)


async def _post(path: str, **kw) -> dict:
    """POST with retries — flaky DNS/keepalive must never crash a command."""
    tries = 3
    for attempt in range(tries):
        try:
            resp = await _HTTP.post(path, **kw)
            try:
                return resp.json()
            except Exception:  # noqa: BLE001
                return {"ok": False, "description": resp.text[:200]}
        except Exception as e:  # noqa: BLE001
            if attempt == tries - 1:
                return {"ok": False, "description": repr(e)[:200]}
            await asyncio.sleep(0.8 * (attempt + 1))


async def _api(method: str, **params) -> dict:
    return await _post(f"{API_URL}/{method}", json=params)


async def _api_multipart(method: str, data: dict, files: dict) -> dict:
    return await _post(f"{API_URL}/{method}", data=data, files=files)


async def send_audio(chat_id: int, filepath: str, caption: str = "",
                     thumb: str | None = None, title: str = "",
                     performer: str = "") -> dict:
    data = {"chat_id": chat_id, "caption": caption, "title": title,
            "performer": performer}
    files = {"audio": open(filepath, "rb")}
    if thumb:
        data["thumbnail"] = "attach://thumb"
        files["thumb"] = open(thumb, "rb")
    return await _api_multipart("sendAudio", data, files)


async def send_video(chat_id: int, filepath: str, caption: str = "",
                     duration: int = 0, width: int = 0, height: int = 0,
                     thumb: str | None = None, streaming: bool = True) -> dict:
    data = {"chat_id": chat_id, "caption": caption, "duration": duration,
            "width": width, "height": height,
            "supports_streaming": str(streaming)}
    files = {"video": open(filepath, "rb")}
    if thumb:
        data["thumbnail"] = "attach://thumb"
        files["thumb"] = open(thumb, "rb")
    return await _api_multipart("sendVideo", data, files)



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
        resp = await _HTTP.head(url)
        return resp.status_code == 200
    except Exception:
        return True


async def send_rich(chat_id: int, html: str, reply_markup=None) -> int | None:
    """Send a rich message; returns the new message id (or None)."""
    params = {"chat_id": chat_id, "rich_message": {"html": _beautify(html)}}
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    j = await _api("sendRichMessage", **params)
    if not j.get("ok"):
        return None
    return j["result"]["message_id"]


async def edit_rich(chat_id: int, message_id: int, html: str, reply_markup=None) -> bool:
    params = {"chat_id": chat_id, "message_id": message_id,
              "rich_message": {"html": _beautify(html)}}
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    j = await _api("editMessageText", **params)
    if not j.get("ok") and "not modified" in str(j.get("description") or ""):
        return True
    return bool(j.get("ok"))


async def edit_reply_markup(chat_id: int, message_id: int, reply_markup) -> bool:
    """Edit only the inline keyboard of a message (preserves custom-emoji icons)."""
    j = await _api("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
                   reply_markup=reply_markup)
    return bool(j.get("ok"))


async def delete_msg(chat_id: int, message_id: int) -> bool:
    j = await _api("deleteMessage", chat_id=chat_id, message_id=message_id)
    return bool(j.get("ok"))


async def answer_callback(cq_id: str, text: str = "", alert: bool = False) -> bool:
    j = await _api("answerCallbackQuery", callback_query_id=cq_id, text=text,
                   show_alert=alert)
    return bool(j.get("ok"))


class RichMystic:
    """Drop-in status-message adapter for code that expects a pyrogram Message.

    edit_text/delete/reply_text map onto the HTTP rich-message helper, so
    stream()/helpers can drive a rich card instead of a plain text bubble.
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


async def status_card(chat_id: int, text: str) -> RichMystic:
    """Send a rich 'working on it...' card and return its adapter handle."""
    mid = await send_rich(chat_id, f"<p>{rich_esc(text)}</p>")
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
    row-blind: first try the Bot API rich edit, then the classic edit.
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
