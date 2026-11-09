# All rights reserved.
#
# Hard safety locks for the AI layer.
#
#   1. Secret redaction: every value the process was started with that looks
#      like a credential is liquidated from any text (prompt or reply) before
#      it leaves the module. The model never sees a token, and even if it
#      parrots one back the scrubber eats it first.
#   2. Pattern bank: key shapes (bot tokens, api hashes, db URIs, provider
#      keys) are scrubbed even when the value itself is unknown.
#   3. Injection shield: user text and chat history are wrapped as inert data
#      the system prompt forbids following.
#   4. Rate limits: hourly budget + cooldown per chat/user.
#   5. Prompt size caps: both directions bounded.
#   6. Kill switch: owner off-switch, backed by Mongo so it survives restarts.
#
# There are NO file-write, shell, or config-change tools anywhere in this
# package - the AI cannot modify the bot, read .env, or run commands BY
# DESIGN, not by instruction.

import os
import re
import time


# ---------------------------------------------------------------- redaction

_SECRET_KEY_RE = re.compile(
    r"(TOKEN|API_HASH|API_ID|KEY|SECRET|PASS|URI|SESSION|COOKIE)", re.I
)
# Keys whose values are identifiers (chat ids, limits) rather than secrets.
_SAFE_KEY_RE = re.compile(r"(_LIMIT|_TIMEOUT|_MAX|_MIN|OWNER_ID|_URL$|DEBUG|PORT)", re.I)


def _collect_values() -> list:
    """
    Everything secret the process knows: .env is injected into the process
    environment by systemd, so this catches every credential the bot holds
    (bot token, api id/hash, mongo uri, provider keys, cookie paths, etc).
    """
    out = set()
    for key, value in os.environ.items():
        if not value or len(value) < 8:
            continue
        if _SAFE_KEY_RE.search(key) or not _SECRET_KEY_RE.search(key):
            continue
        out.add(value.strip())
    try:
        cookies = open("/var/lib/venom-api/cookies/youtube.txt", "rb").read()
        if len(cookies) > 20:
            out.add(cookies[:64].decode("utf-8", "ignore"))
            out.add(cookies[-64:].decode("utf-8", "ignore"))
    except Exception:
        pass
    return sorted(out, key=len, reverse=True)


_VALUES = _collect_values()

# Structural patterns: caught even for a credential that entered the process
# through a channel this module does not know about.
_PATTERN_BANK = [
    (re.compile(r"\b\d{9,12}:[A-Za-z0-9_-]{30,}\b"), "<redacted-bot-token>"),
    (re.compile(r"mongodb(\+srv)?://\S+"), "<redacted-db-uri>"),
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "<redacted-api-key>"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"), "<redacted-gemini-key>"),
    (re.compile(r"\b[0-9a-f]{32}\b"), "<redacted-32hex>"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]+"), "Bearer <redacted>"),
    (re.compile(r"(?i)x-api-key:\s*\S+"), "x-api-key: <redacted>"),
    (re.compile(r"(?i)authorization:\s*\S+"), "Authorization: <redacted>"),
]


def redact(text: str) -> str:
    """Strip every credential-shaped value out of a piece of text."""
    if not isinstance(text, str):
        text = str(text)
    for value in _VALUES:
        if value in text:
            text = text.replace(value, "<redacted>")
    for pattern, replacement in _PATTERN_BANK:
        text = pattern.sub(replacement, text)
    return link_guard(text)


# ------------------------------------------------------------ threat guard

# Requests for hacking/phishing/scam help never reach any model: the router
# short-circuits them to a canned refusal before the AI layer is touched.
_THREAT_RE = re.compile(
    r"\b(?:hack\w*|phish\w*|scam\w*|cheat|fraud|keylog\w*|rat\b|trojan\w*|"
    r"malware|virus|exploit\w*|ddos|botnet|crack\w*|steal\w*|bypass\w*|"
    r"otp\b|sim.?swap|carding|dark.?web|trap.?link|fake.?link|"
    r"account.{0,12}(?:hack|chor|paas|do)|password.{0,12}(?:hack|nikal|do))\b",
    re.I | re.UNICODE,
)


def threat(text: str) -> bool:
    """True when the text asks for hacking / phishing / scam assistance."""
    return bool(_THREAT_RE.search(str(text or "")))


# ------------------------------------------------------------ link allowlist

# Only audio-relevant links may survive into a reply. Anything else (and any
# url at all inside streamed data) is neutralised to '[link blocked]'.
_URL_RE = re.compile(r"(?i)\bhttps?://\S+|\b(?:www\.)\S+")
_LINK_OK_RE = re.compile(
    r"(?i)^(?:https?://)?(?:[\w-]*\.)*(?:youtube\.com|youtu\.be|spotify\.com"
    r"|venombolteop\S*)"
)
_LINK_BLOCKED = "[link blocked]"


def link_guard(text: str) -> str:
    """Replace every url that is not an allowlisted music link."""
    def _sub(m):
        url = m.group(0).rstrip(".,?!)];}\"'")
        return _LINK_BLOCKED if not _LINK_OK_RE.match(url) else url
    return _URL_RE.sub(_sub, str(text or ""))


# ---------------------------------------------------------------- input caps

def cap_input(text: str) -> str:
    """Redact + bound any user-supplied text before it reaches a model."""
    from config.config import AI_MAX_INPUT
    return redact(str(text or ""))[: max(AI_MAX_INPUT, 200)]


# ------------------------------------------------------- injection shielding

def shield(text: str) -> str:
    """Neutralise <> so content cannot fake html, and mark it as data."""
    txt = str(text or "").replace("<", "&lt;").replace(">", "&gt;")
    return f"<data>{txt}</data>"


# ---------------------------------------------------------------- rate limit

_buckets: dict = {}
_last: dict = {}


def rate_ok(key: str, limit: float, cooldown: float) -> bool:
    """
    True when the caller still has hourly budget and is not on cooldown.
    ``key`` is chat/user scoped, so one spammer never empties the chat.
    """
    now = time.monotonic()
    if now - _last.get(key, 0) < cooldown:
        return False
    window, used = _buckets.get(key, (now, 0))
    if now - window >= 3600:
        window, used = now, 0
    if used >= limit:
        return False
    _buckets[key] = (window, used + 1)
    _last[key] = now
    return True


def reset_rate(key: str) -> None:
    _buckets.pop(key, None)
    _last.pop(key, None)


# ---------------------------------------------------------------- audits

def audit_note(bot_label: str, event: str, detail: str) -> str:
    """One-line audit trail entry (no timeline, only what happened)."""
    return f"[{bot_label}] {event} :: {redact(detail)[:240]}"
