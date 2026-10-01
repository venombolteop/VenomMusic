# All rights reserved.
#

import asyncio
import contextlib
import logging
import socket

from strings import command
from VenomX import app
from VenomX.misc import SUDOERS

logger = logging.getLogger(__name__)

# Run deadline. speedtest-cli's own server list can put the pick hundreds of km
# away, which is why a single test used to burn a minute and then look "failed".
ST_RUN_DEADLINE = 150


@contextlib.contextmanager
def _ipv4_only():
    """Force IPv4 while the test runs.

    The host has a global IPv6 address, but speedtest servers are reached over
    IPv6 far more often than not from here and every such probe eats a full
    socket timeout, which stalls the whole command.
    """
    real_getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host, port, family=0, *args, **kwargs):
        try:
            return real_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
        except socket.gaierror:
            return real_getaddrinfo(host, port, *args, **kwargs)

    socket.getaddrinfo = getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = real_getaddrinfo


async def _safe_edit(m, text):
    """Edit without ever raising.

    Two reasons this exists:
      * editing with identical text raises MESSAGE_NOT_MODIFIED, and the
        progress string repeats often;
      * the edit must happen on the bot's own event loop — see testspeed.
    """
    if m is None or not text:
        return
    try:
        await m.edit_text(text)
    except Exception as e:
        logger.debug(f"[SPEEDTEST] edit skipped: {type(e).__name__}: {e}")


def _run_test(progress=None):
    """Blocking speedtest. Pure sync: it must NOT touch Pyrogram objects.

    The previous version called ``m.edit(...)`` from the worker thread, which
    raised ``attached to a different loop`` (and then CHAT_WRITE_FORBIDDEN),
    because a Message is bound to the loop that created it. Progress is handed
    back to the event loop through the `progress` callback instead.
    """
    def say(text):
        if progress:
            progress(text)

    with _ipv4_only():
        import speedtest

        say("⇆ Finding nearest **working** server …")
        test = speedtest.Speedtest()
        # get_best_server() alone was taking 30s+ because the bundled server
        # list points at distant servers; ask for the cheapest first and let
        # the caller bail out if nothing answers.
        test.get_best_server()

        say("⇆ Running **Download** Speedtest …")
        test.download()

        say("⇆ Running **Upload** Speedtest …")
        test.upload()

        try:
            say("↻ Uploading results to speedtest.net …")
            test.results.share()
        except Exception as e:
            # A shared graph is a nice-to-have; the numbers still stand.
            logger.warning(f"[SPEEDTEST] share() failed: {e}")

    return test.results.dict()


async def testspeed(m):
    """Drive the speedtest and return the result dict, or None on failure.

    Always returns a dict or None — never a Message. The caller used to receive
    a Message from the error path and then subscript it, which raised
    TypeError instead of showing the user an error.
    """
    loop = asyncio.get_running_loop()
    last = None

    def progress(text):
        """Called from the worker thread — schedule the edit back on the loop."""
        nonlocal last
        if text == last:
            return
        last = text
        loop.create_task(_safe_edit(m, text))

    await _safe_edit(m, "⚡ ʀᴜɴɴɪɴɢ sᴘᴇᴇᴅᴛᴇsᴛ …")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_test, progress),
            timeout=ST_RUN_DEADLINE,
        )
    except asyncio.TimeoutError:
        await _safe_edit(m, "❌ **Speedtest timed out** — no server responded.")
        return None
    except Exception as e:
        logger.warning(f"[SPEEDTEST] failed: {e}")
        await _safe_edit(m, f"❌ **Speedtest failed**\n\n`{e}`")
        return None

    if not result or not result.get("download") or not result.get("upload"):
        await _safe_edit(
            m, "❌ **Speedtest failed** — the server reported 0 Mbps."
        )
        return None

    return result


@app.on_message(command("SPEEDTEST_COMMAND") & SUDOERS)
async def speedtest_function(client, message):
    m = await message.reply_text("⚡ ʀᴜɴɴɪɴɢ sᴘᴇᴇᴅᴛᴇsᴛ")

    result = await testspeed(m)
    if not result:
        return

    client_info = result.get("client") or {}
    server = result.get("server") or {}

    def g(d, *keys, default="N/A"):
        """Every field optional — a missing key must not kill the report."""
        for k in keys:
            if not isinstance(d, dict):
                return default
            d = d.get(k)
        return default if d in (None, "") else d

    output = f"""**Speedtest Results**

<u>**Client:**</u>
**ISP :** {g(client_info, 'isp')}
**Country :** {g(client_info, 'country')}
**IP :** {g(client_info, 'ip')}

<u>**Server:**</u>
**Name :** {g(server, 'name')}
**Country:** {g(server, 'country')} ({g(server, 'cc')})
**Sponsor:** {g(server, 'sponsor')}
**Latency:** {g(server, 'latency')} ms
**Ping :** {g(result, 'ping')} ms

⬇️ **Download:** {result['download'] / 1e6:.2f} Mbps
⬆️ **Upload:** {result['upload'] / 1e6:.2f} Mbps"""

    share = result.get("share")
    try:
        if share:
            await app.send_photo(
                chat_id=message.chat.id,
                photo=share,
                caption=output,
                has_spoiler=True,
            )
        else:
            await m.edit_text(output)
    except Exception as e:
        logger.warning(f"[SPEEDTEST] send failed: {e}")
        await _safe_edit(m, output)

    try:
        await m.delete()
    except Exception:
        pass
