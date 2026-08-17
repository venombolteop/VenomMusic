"""
Security filter — intercepts command injection payloads, exfil attempts,
and malicious URLs before any other handler sees them.
Runs at group=-2 so it executes before everything else.
"""

import re
from urllib.parse import unquote

from pyrogram import filters

import config
from VenomX import app, LOGGER

_LOG = LOGGER(__name__)

# --- Patterns that indicate command injection / env exfil ---

# Raw (decoded) patterns
_RAW_PATTERNS = [
    re.compile(r"\$\(", re.IGNORECASE),                          # $() command substitution
    re.compile(r"\$\{IFS\}", re.IGNORECASE),                     # ${IFS}
    re.compile(r"printenv", re.IGNORECASE),                       # env dump
    re.compile(r"curl\s+.*--data-binary", re.IGNORECASE),        # curl exfil
    re.compile(r"curl\s+.*-d\s", re.IGNORECASE),                 # curl -d
    re.compile(r"wget\s+.*--post", re.IGNORECASE),               # wget exfil
    re.compile(r">\s*/dev/tcp", re.IGNORECASE),                   # bash reverse shell
    re.compile(r"base64\s+--decode", re.IGNORECASE),             # base64 decode in command
    re.compile(r"eval\s*\(", re.IGNORECASE),                      # eval() injection
    re.compile(r"exec\s*\(", re.IGNORECASE),                      # exec() injection
    re.compile(r"os\.system\s*\(", re.IGNORECASE),               # python os.system
    re.compile(r"subprocess", re.IGNORECASE),                     # python subprocess
    re.compile(r"__import__\s*\(", re.IGNORECASE),               # python __import__
]

# URL-encoded patterns (decoded before checking)
_URL_ENCODED_PATTERNS = [
    re.compile(r"%7BIFS%7D", re.IGNORECASE),   # ${IFS}
    re.compile(r"%7C", re.IGNORECASE),           # |
    re.compile(r"%24", re.IGNORECASE),           # $
    re.compile(r"%28", re.IGNORECASE),           # (
    re.compile(r"%29", re.IGNORECASE),           # )
    re.compile(r"%60", re.IGNORECASE),           # `
    re.compile(r"%3B", re.IGNORECASE),           # ;
]

# Suspicious hosting + command combo (catches railway, heroku, etc.)
_EXFIL_DOMAINS = re.compile(
    r"(railway\.app|herokuapp\.com|vercel\.app|glitch\.me|"
    r"onrender\.com|fly\.dev|repl\.co|"
    r"web-production-[a-z0-9]+\.up\.railway)",
    re.IGNORECASE,
)


def _is_malicious(text: str) -> bool:
    """Check if text contains command injection / exfil payload."""
    if not text:
        return False

    # Check raw patterns directly
    for pat in _RAW_PATTERNS:
        if pat.search(text):
            return True

    # Decode URL encoding and re-check
    decoded = unquote(unquote(text))
    if decoded != text:
        for pat in _RAW_PATTERNS:
            if pat.search(decoded):
                return True
        for pat in _URL_ENCODED_PATTERNS:
            if pat.search(decoded):
                return True

    # Check if suspicious domain appears in a URL with shell-like content
    if _EXFIL_DOMAINS.search(text):
        # If there's a $() or shell metacharacter near the domain, flag it
        combined = text + decoded
        if any(c in combined for c in ["$(", "${", "|$", "&&$", "`"]):
            return True
        # Also flag any URL that encodes shell chars near these domains
        if _URL_ENCODED_PATTERNS[0].search(decoded):  # %7BIFS%7D
            return True

    return False


@app.on_message(filters.all, group=-2)
async def security_filter(client, message):
    """Block malicious payloads and alert the owner."""
    try:
        # Gather all possible text sources
        texts = []
        if message.text:
            texts.append(message.text)
        if message.caption:
            texts.append(message.caption)

        # Also check command args
        if message.command:
            texts.extend(message.command)

        full_text = " ".join(texts)
        if not _is_malicious(full_text):
            return

        # --- Malicious payload detected ---
        user = message.from_user
        chat = message.chat

        user_info = (
            f"User: {user.first_name or 'N/A'} (ID: {user.id})\n"
            f"Username: @{user.username or 'none'}\n"
        ) if user else "User: Unknown (no from_user)\n"

        chat_info = (
            f"Chat: {chat.title or 'N/A'} (ID: {chat.id})\n"
            f"Type: {chat.type}\n"
        ) if chat else "Chat: N/A\n"

        msg_text = message.text or message.caption or "(no text)"

        alert = (
            "🛡 <b>SECURITY ALERT — Malicious payload blocked</b>\n\n"
            f"{user_info}"
            f"{chat_info}"
            f"<b>Message:</b>\n<code>{msg_text[:3000]}</code>\n\n"
            f"⚠️ Forwarded for review."
        )

        # Forward original message to owner
        try:
            await message.forward(config.OWNER_ID[0])
        except Exception:
            pass

        # Send alert summary to owner
        try:
            await app.send_message(
                config.OWNER_ID[0],
                alert,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        _LOG.warning(
            "BLOCKED malicious payload from user=%s chat=%s: %s",
            user.id if user else "?",
            chat.id if chat else "?",
            msg_text[:200],
        )

        # Delete the message from chat
        try:
            await message.delete()
        except Exception:
            pass

    except Exception as e:
        _LOG.error("Security filter error: %s", e)
