# All rights reserved.
#
# Now-playing rich card with a live progress bar.
#
# The card is a TEXT rich message (Bot API 10.3): buttons live in the message
# HTML, so the classic photo card is gone. A background refresher re-renders
# the bar every ~18s straight from db[chat_id][0]["played"] (the 1s tick in
# seeker.timer), so pause/resume/seek stay honest.
#

import asyncio
import time

from VenomX.misc import db
from VenomX.utils.inline.play import get_progress_bar
from VenomX.utils.rich_msg import (
    RichMystic,
    edit_rich,
    pemoji,
    rich_note,
    rich_url_button,
    rich_button,
    rich_button_row,
    rich_esc,
    rich_heading,
    rich_kv,
    rich_img,
    send_rich,
)

_TICK = 18

_panel_content = {}
_closed_panels = set()
_menu_page: dict = {}


def mark_panel_closed(chat_id: int, message_id: int) -> None:
    """Stop the refresher when the panel is closed/replaced."""
    _closed_panels.add((chat_id, message_id))
    _panel_content.pop((chat_id, message_id), None)
    _menu_page.pop((chat_id, message_id), None)


def _bar_style(percentage: float) -> str:
    pct = int(percentage) if percentage else 0
    if pct <= 10:
        return "primary"
    if pct < 25:
        return "success"
    if pct < 40:
        return "danger"
    if pct < 55:
        return "primary"
    if pct < 70:
        return "success"
    if pct < 85:
        return "danger"
    return "primary"


def _ctl_style() -> str:
    # Keep the skip button style stable across periodic panel refreshes.
    return "primary"


def _toggle_button(chat_id: int) -> str:
    """Single play/pause toggle — label shows the ACTION next press performs."""
    if db.get(chat_id):
        return rich_button(
            f"{pemoji('⏸')} ᴘᴀᴜsᴇ",
            callback_data=f"ADMIN Pp|{chat_id}",
            style="danger",
        )
    return rich_button(
        f"{pemoji('▶')} ᴘʟᴀʏ",
        callback_data=f"ADMIN Pp|{chat_id}",
        style="success",
    )


def _rows(chat_id: int, videoid, elapsed: float, total_sec: float, playing: bool = True) -> str:
    try:
        from VenomX.utils.formatters import seconds_to_min

        played_txt = seconds_to_min(int(elapsed or 0))
    except Exception:
        played_txt = "00:00"

    try:
        dur_txt = seconds_to_min(int(total_sec)) if total_sec else "--:--"
    except Exception:
        dur_txt = "--:--"

    pct = (int(elapsed or 0) / total_sec * 100) if total_sec else 0
    bar = get_progress_bar(pct)

    bar_label = f"{pemoji('⏳')} {played_txt} {bar} {dur_txt}"
    rows = rich_button_row(
        rich_button(bar_label, callback_data="GetTimer", style=_bar_style(pct)),
        align="center",
    )

    rows += rich_button_row(
        rich_button(f"{pemoji('🗂')} Qᴜᴇᴜᴇ", callback_data=f"GetQueued {chat_id}|{videoid}", style="success"),
        rich_button(f"{pemoji('➕')} ᴘʟᴀʏʟɪꜱᴛ", callback_data=f"add_playlist {videoid}", style="primary"),
        align="center",
    )
    rows += rich_button_row(
        rich_button(f"{pemoji('⚙')} ᴍᴇɴᴜ", callback_data=f"PanelMarkup {videoid}|{chat_id}", style="primary"),
        rich_button(f"{pemoji('❌')} ᴄʟᴏꜱᴇ", callback_data="close", style="danger"),
        align="center",
    )
    rows += rich_button_row(
        _toggle_button(chat_id),
        rich_button(f"{pemoji('⏩')} sᴋɪᴘ", callback_data=f"ADMIN Skip|{chat_id}", style=_ctl_style()),
        rich_button(f"{pemoji('🛑')} sᴛᴏᴘ", callback_data=f"ADMIN Stop|{chat_id}", style="danger"),
        align="center",
    )
    return rows


def _body(_, title: str, duration_min: str, user_name: str, thumb=None) -> str:
    body = rich_heading(f'{pemoji("🎧")} ᴠᴇɴᴏᴍ ɴᴏᴡ ᴘʟᴀʏɪɴɢ', level=4)
    thumb_url = str(thumb) if thumb else ""
    if thumb_url.startswith(("http://", "https://")):
        body += rich_img(thumb_url)
    body += "<hr/>"
    # Pull-quote card: centered track info with highlighted values.
    body += (
        "<aside>"
        f"{pemoji('🎵')} <b>{rich_esc(str(title)[:34])}</b><br>"
        f"{pemoji('⏱')} <mark>{rich_esc(duration_min)} ᴍɪɴꜱ</mark>"
        f"  ·  {pemoji('🎤')} {rich_esc(user_name)}"
        "</aside>"
    )
    body += f"<footer>{pemoji('📡')} ᴠᴇɴᴏᴍ ᴘʀᴇᴍɪᴜᴍ ᴠᴏɪᴄᴇ ꜱᴛʀᴇᴀᴍ</footer>"
    body += rich_button_row(
        rich_url_button(f"{pemoji('💬')} ꜱᴜᴘᴘᴏʀᴛ", "https://t.me/venom_chatting"),
        align="center",
    )
    return body


async def _send_card(chat_id: int, html: str) -> int | None:
    return await send_rich(chat_id, html)


def _register(chat_id: int, mid: int, videoid, total_sec: float):
    playing = db.get(chat_id)
    if playing:
        playing[0]["mystic"] = RichMystic(chat_id, mid)
        playing[0]["markup"] = "rich"
        playing[0]["rich_mid"] = mid


async def _maxres(videoid, thumb) -> str | None:
    """Prefer YouTube maxresdefault; fall back to whatever we already have."""
    candidate = f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"
    if not videoid:
        return thumb
    if thumb and "img.youtube" not in str(thumb):
        return thumb
    from VenomX.utils.rich_msg import url_ok

    if await url_ok(candidate):
        return candidate
    return thumb or candidate.replace("maxresdefault", "hqdefault")


async def spawn_now_playing(
    _,
    chat_id: int,
    videoid,
    title: str,
    duration_min: str,
    user_name: str,
    thumb=None,
) -> int | None:
    """Send the now-playing rich card, register it on the db and start ticking."""
    playing = db.get(chat_id)
    total_sec = playing[0].get("seconds", 0) if playing else 0
    try:
        total_sec = float(total_sec or 0)
    except Exception:
        total_sec = 0
    thumb = await _maxres(videoid, thumb)
    body = _body(_, title, duration_min, user_name, thumb)
    mid = await _send_card(chat_id, body + _rows(chat_id, videoid, 0, total_sec))
    if not mid:
        return None
    _panel_content[(chat_id, mid)] = (body, videoid, total_sec, time.time())
    _register(chat_id, mid, videoid, total_sec)
    asyncio.create_task(
        _ticker(chat_id, mid, videoid, body, _panel_content[(chat_id, mid)])
    )
    return mid


async def _ticker(chat_id: int, mid: int, videoid, body: str, snapshot: tuple) -> None:
    _body_s, videoid, total_sec, start_t = snapshot
    entry = _panel_content.get((chat_id, mid))
    if entry:
        start_t = entry[3]
    try:
        dur_float = float(total_sec or 0)
    except Exception:
        dur_float = 0
    while (chat_id, mid) not in _closed_panels:
        await asyncio.sleep(_TICK)
        if (chat_id, mid) in _closed_panels:
            break
        playing = db.get(chat_id)
        if not playing or playing[0].get("rich_mid") != mid:
            break
        if (chat_id, mid) in _menu_page:
            continue
        played = float(playing[0].get("played", 0) or 0)
        html = body + _rows(chat_id, videoid, played, dur_float, playing=True)
        await edit_rich(chat_id, mid, html)
        if dur_float and played >= dur_float:
            break


async def refresh_after_toggle(chat_id: int, message_id: int, paused: bool) -> bool:
    """Re-render after a play/pause toggle, honouring an open menu page."""
    page = _menu_page.get((chat_id, message_id))
    if page is not None:
        playing = db.get(chat_id)
        videoid = playing[0].get("vidid") if playing else None
        return await show_menu(None, chat_id, message_id, videoid, page)
    return await refresh_panel(chat_id, message_id, paused)


async def refresh_panel(chat_id: int, message_id: int, paused: bool = False) -> bool:
    """Re-render the panel after pause/seek/state changes."""
    playing = db.get(chat_id)
    if not playing:
        return False
    if (chat_id, message_id) in _menu_page:
        return True
    cached = _panel_content.get((chat_id, message_id))
    videoid = playing[0].get("vidid")
    total_sec = playing[0].get("seconds") or 0
    title = (playing[0].get("title") or "").title()
    duration_min = playing[0].get("dur") or "--:--"
    user_name = playing[0].get("by") or "venom"
    body = cached[0] if cached else _body(None, title, duration_min, user_name)
    played = float(playing[0].get("played", 0) or 0)
    return await edit_rich(
        chat_id, message_id, body + _rows(chat_id, videoid, played, total_sec, playing=not paused)
    )


async def replace_panel(chat_id: int, message_id: int, text: str) -> bool:
    """Kill the ticker and leave a short status line on the old panel."""
    mark_panel_closed(chat_id, message_id)
    return await edit_rich(chat_id, message_id, f"<p>{rich_esc(text)}</p>")


async def snapshot_card(chat_id: int) -> int | None:
    """Re-send an up-to-date now-playing card without touching the live panel.

    Used by the mirror command (/player): the active panel keeps ticking,
    this is a read-only copy built straight from db state.
    """
    playing = db.get(chat_id)
    if not playing:
        return None
    videoid = playing[0].get("vidid")
    try:
        total_sec = float(playing[0].get("seconds") or 0)
    except Exception:
        total_sec = 0
    title = (playing[0].get("title") or "Unknown").title()
    duration_min = playing[0].get("dur") or "--:--"
    user_name = playing[0].get("by") or "venom"
    thumb = await _maxres(videoid, None)
    body = _body(None, title, duration_min, user_name, thumb)
    played = float(playing[0].get("played", 0) or 0)
    return await _send_card(chat_id, body + _rows(chat_id, videoid, played, total_sec))


async def notice_card(
    _,
    chat_id: int,
    heading: str,
    body_text: str,
    thumb=None,
) -> int | None:
    """Small rich notice card (added-to-queue, playlist done, etc.)."""
    html = rich_heading(f"{pemoji('🎵')} {rich_esc(heading)}", level=4)
    if thumb:
        html += rich_img(thumb)
    if body_text:
        html += rich_note(rich_esc(body_text).replace("\n", "<br>"))
    html += rich_button_row(
        rich_button(f"{pemoji('❌')} ᴄʟᴏꜱᴇ", callback_data="close", style="danger"),
        align="center",
    )
    return await _send_card(chat_id, html)


async def _ensure_body(_, chat_id: int, mid: int, videoid) -> tuple[str, float]:
    """Cached card body, or a rebuild from db (restart-surviving panels)."""
    cached = _panel_content.get((chat_id, mid))
    if cached:
        return cached[0], cached[2]
    playing = db.get(chat_id)
    total_sec = 0.0
    title, duration_min, user_name = "Unknown", "--:--", "venom"
    if playing:
        try:
            total_sec = float(playing[0].get("seconds") or 0)
        except Exception:
            total_sec = 0
        title = (playing[0].get("title") or "Unknown").title()
        duration_min = playing[0].get("dur") or "--:--"
        user_name = playing[0].get("by") or "venom"
    thumb = await _maxres(videoid, None)
    return _body(_, title, duration_min, user_name, thumb), total_sec


async def show_menu(_, chat_id: int, mid: int, videoid, page: int) -> bool:
    """Open a menu page on the rich panel; False if the message is not rich."""
    body, _t = await _ensure_body(_, chat_id, mid, videoid)
    ok = await edit_rich(chat_id, mid, body + menu_pages_rows(_, videoid, chat_id, page))
    if ok:
        _menu_page[(chat_id, mid)] = page
    return ok


async def show_main(chat_id: int, mid: int, videoid, playing: bool = True) -> bool:
    """Leave the menu and re-render the main progress rows."""
    body, total_sec = await _ensure_body(None, chat_id, mid, videoid)
    played = 0.0
    cur = db.get(chat_id)
    if cur:
        played = float(cur[0].get("played", 0) or 0)
    ok = await edit_rich(
        chat_id, mid, body + _rows(chat_id, videoid, played, total_sec, playing=playing)
    )
    if ok:
        _menu_page.pop((chat_id, mid), None)
    return ok


def menu_pages_rows(_, videoid, chat_id: int, page: int) -> str:
    """The 3-page player menu (controls / volume+shuffle / seek) as rich rows."""
    yellow = f"Pages Back|{page}|{videoid}|{chat_id}"
    fuzzy = f"MainMarkup {videoid}|{chat_id}"
    nav = rich_button_row(
        rich_button(f"{pemoji('⬅')} ᴘʀᴇᴠ", callback_data=f"Pages Back|{page}|{videoid}|{chat_id}", style="primary"),
        rich_button(f"{pemoji('🚀')} ʙᴀᴄᴋ", callback_data=fuzzy, style="primary"),
        rich_button(f"{pemoji('➡')} ɴᴇxᴛ", callback_data=f"Pages Forw|{page}|{videoid}|{chat_id}", style="primary"),
        align="center",
    )
    if page == 0:
        rows = (
            rich_button_row(_toggle_button(chat_id))
            + rich_button_row(
                rich_button(f"{pemoji('⏩')} sᴋɪᴘ", callback_data=f"ADMIN Skip|{chat_id}", style=_ctl_style()),
                rich_button(f"{pemoji('🛑')} sᴛᴏᴘ", callback_data=f"ADMIN Stop|{chat_id}", style="danger"),
            )
            + rich_button_row(
                rich_button(f"{pemoji('🔁')} ʀᴇᴘʟᴀʏ", callback_data=f"ADMIN Loop|{chat_id}", style="success"),
            )
        )
    elif page == 1:
        rows = (
            rich_button_row(
                rich_button(f"{pemoji('🔇')} ᴍᴜᴛᴇ", callback_data=f"ADMIN Mute|{chat_id}", style="primary"),
                rich_button(f"{pemoji('🔊')} ᴜɴᴍᴜᴛᴇ", callback_data=f"ADMIN Unmute|{chat_id}", style="success"),
            )
            + rich_button_row(
                rich_button(f"{pemoji('🎲')} ꜱʜᴜꜰꜰʟᴇ", callback_data=f"ADMIN Shuffle|{chat_id}", style="danger"),
                rich_button(f"{pemoji('🔁')} ʟᴏᴏᴘ", callback_data=f"ADMIN Loop|{chat_id}", style="primary"),
            )
        )
    else:
        rows = (
            rich_button_row(
                rich_button(f"{pemoji('⏪')} 10ꜱ ʙᴀᴄᴋ", callback_data=f"ADMIN 1|{chat_id}", style="primary"),
                rich_button(f"{pemoji('⏩')} 10ꜱ ғᴏʀᴡᴀʀᴅ", callback_data=f"ADMIN 2|{chat_id}", style="primary"),
            )
            + rich_button_row(
                rich_button(f"{pemoji('⏪')} 30ꜱ ʙᴀᴄᴋ", callback_data=f"ADMIN 3|{chat_id}", style="primary"),
                rich_button(f"{pemoji('⏩')} 30ꜱ ғᴏʀᴡᴀʀᴅ", callback_data=f"ADMIN 4|{chat_id}", style="primary"),
            )
        )
    return rows + nav

async def reattach_from_db(_, chat_id: int, mid: int) -> bool:
    """Rebuild the now-playing panel on an existing message and restart the ticker."""
    playing = db.get(chat_id)
    if not playing:
        return False
    videoid = playing[0].get("vidid")
    try:
        total_sec = float(playing[0].get("seconds") or 0)
    except Exception:
        total_sec = 0
    title = (playing[0].get("title") or "").title()
    duration_min = playing[0].get("dur") or "--:--"
    user_name = playing[0].get("by") or "venom"
    thumb = await _maxres(videoid, None)
    body = _body(_, title, duration_min, user_name, thumb)
    played = float(playing[0].get("played", 0) or 0)
    ok = await edit_rich(chat_id, mid, body + _rows(chat_id, videoid, played, total_sec))
    if ok:
        _closed_panels.discard((chat_id, mid))
        _menu_page.pop((chat_id, mid), None)
        _panel_content[(chat_id, mid)] = (body, videoid, total_sec, time.time())
        _register(chat_id, mid, videoid, total_sec)
        asyncio.create_task(
            _ticker(chat_id, mid, videoid, body, _panel_content[(chat_id, mid)])
        )
    return ok
