
# All rights reserved.
#

from strings import command
from VenomX import app
from VenomX.misc import SUDOERS
from VenomX.utils.database import autoend_off, autoend_on


@app.on_message(command("AUTOEND_COMMAND") & SUDOERS)
async def auto_end_stream(client, message):
    usage = "**ᴜsᴀɢᴇ:**\n\n/autoend [enable|disable]"
    if len(message.command) != 2:
        return await message.reply_text(usage)
    state = message.text.split(None, 1)[1].strip()
    state = state.lower()
    if state == "enable":
        await autoend_on()
        await message.reply_text(
            "Auto End enabled.\n\nBot will leave voicechat automatically after 30 secinds if one is listening song with a warning message.."
        )
    elif state == "disable":
        await autoend_off()
        await message.reply_text("Autoend disabled")
    else:
        await message.reply_text(usage)
