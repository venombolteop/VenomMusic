
# All rights reserved.
#


import config
from strings import command
from VenomX import app
from VenomX.misc import SUDOERS
from VenomX.utils.database import add_off, add_on
from VenomX.utils.decorators.language import language
from VenomX.utils.rich_msg import reply_note, status_card


@app.on_message(command("LOGGER_COMMAND") & SUDOERS)
@language
async def logger(client, message, _):
    usage = _["log_1"]
    if len(message.command) != 2:
        return await reply_note(message, usage)
    state = message.text.split(None, 1)[1].strip()
    state = state.lower()
    if state == "enable":
        await add_on(config.LOG)
        await reply_note(message, _["log_2"])
    elif state == "disable":
        await add_off(config.LOG)
        await reply_note(message, _["log_3"])
    else:
        await reply_note(message, usage)
