
# All rights reserved.
#

from pyrogram.types import Message

from strings import command
from VenomX import app
from VenomX.misc import SUDOERS
from VenomX.utils.database import set_video_limit
from VenomX.utils.decorators.language import language
from VenomX.utils.rich_msg import reply_note, status_card


@app.on_message(command("VIDEOLIMIT_COMMAND") & SUDOERS)
@language
async def set_video_limit_kid(client, message: Message, _):
    if len(message.command) != 2:
        usage = _["vid_1"]
        return await reply_note(message, usage)
    message.chat.id
    state = message.text.split(None, 1)[1].strip()
    if state.lower() == "disable":
        limit = 0
        await set_video_limit(limit)
        return await reply_note(message, _["vid_4"])
    if state.isnumeric():
        limit = int(state)
        await set_video_limit(limit)
        if limit == 0:
            return await reply_note(message, _["vid_4"])
        await reply_note(message, _["vid_3"].format(limit))
    else:
        return await reply_note(message, _["vid_2"])
