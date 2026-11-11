# The group AI chatbot: a per-chat toggle that makes the bot answer plain
# conversation with no command prefix at all. Same safety rails as /ai:
# threat refusal before any model call, secret redaction on everything that
# reaches storage or the chat, per-user cooldown plus an hourly budget so a
# group cannot be flooded.

import time

from pyrogram import filters

from config import BANNED_USERS
from strings import command
from VenomX import app
from VenomX.utils.ai import brain
from VenomX.utils.ai import enabled as ai_enabled
from VenomX.utils.ai import memory as mem
from VenomX.utils.ai.safety import redact, threat
from VenomX.utils.rich_msg import (
    edit_rich,
    md_to_rich,
    send_rich,
    status_card,
)

_LOGO = "🤖"
_ERR = "cockpit se jawab nahi mila — thodi der baaad."
_ON = (
    f"{_LOGO} <b><mark>AI Chat ON</mark></b>\n"
    "<blockquote>Ab kuch bhi bolo — bina command ke jawab dungi 🤌</blockquote>\n"
    "<footer>Off karne ke liye <code>/chatbot off</code></footer>"
)
_OFF = "🤖 <b>AI chat off.</b> Phir /ai se jaldi milte hai."

SYSTEM = (
    "You are Venom, a friendly group chatbot in a Telegram music group. "
    "LANGUAGE RULE: answer in whatever language the sender wrote in "
    "(Hinglish for Hinglish, English for English); mirror their words, never "
    "switch to a different script on your own.\n"
    "Style: short, casual, like a friend in the group chat — under 60 words, "
    "no lists, no headings, plain lines, a light emoji only where it fits.\n"
    "Song requests route through the AI play lane; if someone asks to play "
    "something, answer naturally and tell them to say 'Ai play <song>' for "
    "instant playback.\n"
    "NEVER help with hacking, phishing or scams — refuse with one short "
    "line. Never ask anyone for money, gifts or private photos."
)


# ------------------------------------------------------------------ state

async def chat_on(chat_id: int) -> bool:
    doc = await mem.aisetdb.find_one({"chat_id": chat_id, "key": "chatbot"})
    return bool(doc and doc.get("value"))


async def chat_set(chat_id: int, value: bool) -> str:
    await mem.aisetdb.update_one(
        {"chat_id": chat_id, "key": "chatbot"},
        {"$set": {"value": bool(value)}},
        upsert=True,
    )
    return _ON if value else _OFF


# ------------------------------------------------------------------ toggle

@app.on_message(command("CHATBOT_COMMAND") & ~BANNED_USERS)
async def chatbot_toggle(client, message):
    on, _why = await ai_enabled()
    if not on:
        return await message.reply_text(
            f"{_LOGO} AI off hai is deployment pe.", parse_mode="html"
        )
    want = message.text.lower().split()
    enable = None
    if "on" in want:
        enable = True
    elif "off" in want:
        enable = False
    chat_id = message.chat.id
    if enable is None:
        enable = not await chat_on(chat_id)
    note = await chat_set(chat_id, enable)
    if enable:
        await send_rich(chat_id, note)
    else:
        await message.reply_text(note, parse_mode="html")


# ------------------------------------------------------------------ chatter

_PREFIX_CHARS = "!/?*.,@#_-"


@app.on_message(filters.group & ~BANNED_USERS & filters.text)
async def chatbot_chatter(client, message):
    if message.sender_chat:
        return
    text = (message.text or "").strip()
    if not text or text[0] in _PREFIX_CHARS:
        return
    chat_id = message.chat.id
    if not await chat_on(chat_id):
        return
    on, _why = await ai_enabled()
    if not on:
        return
    uid = message.from_user.id if message.from_user else 0
    if not brain.safety.rate_ok(f"chat:{chat_id}:{uid}", 8, 7):
        return

    if threat(text):
        return await message.reply_text(
            f"{_LOGO} Ye baat me nahi karunga 🛡 — kaam ki baat pucho!",
            parse_mode="html",
        )

    msgs = brain._messages(brain._system(None, SYSTEM), [], text)
    started = time.monotonic()
    mystic = None
    answer = ""
    last = 0.0

    async def show(partial: str) -> None:
        # RichMystic routes edits through the rich-message HTTP API and
        # escapes the text itself — no raw HTML to break parse mode. The
        # card is only posted once there is real text, no lame placeholder.
        nonlocal mystic
        body = f"{_LOGO} {partial[:700]} …"
        try:
            if mystic is None:
                mystic = await status_card(chat_id, body)
            else:
                await mystic.edit_text(body)
        except Exception:
            pass

    try:
        async for delta in brain.stream_chat(msgs):
            answer += delta
            now = time.monotonic()
            if now - last >= 1.6 and len(answer.strip()) > 12:
                last = now
                await show(redact(answer)[:800])
    except Exception:
        if not answer:
            answer = ""

    final = redact(answer or "").strip()
    if not final:
        if mystic is None:
            return
        try:
            await mystic.edit_text(_ERR)
        except Exception:
            pass
        return
    secs = max(1, int(time.monotonic() - started))
    mid = getattr(mystic, "id", None)
    if mid:
        html = (
            "<h3>🤖 AI Chat</h3>"
            + md_to_rich(final[:1200])
            + f"<footer>🤖 {secs}s me reply</footer>"
        )
        try:
            await edit_rich(chat_id, mid, html)
            return
        except Exception:
            pass
    try:
        await mystic.edit_text(f"{_LOGO} {final[:1200]}")
    except Exception:
        pass
