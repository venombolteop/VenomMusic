
# All rights reserved.
#

from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from strings import command
from VenomX import app
from VenomX.utils.database.memorydatabase import get_loop, set_loop
from VenomX.utils.decorators import AdminRightsCheck
from VenomX.utils.rich_msg import reply_note, status_card


@app.on_message(command("LOOP_COMMAND") & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def admins(cli, message: Message, _, chat_id):
    usage = _["admin_24"]
    if len(message.command) != 2:
        return await reply_note(message, usage)
    state = message.command[1].strip()
    if state.isnumeric():
        state = int(state)
        if 1 <= state <= 10:
            got = await get_loop(chat_id)
            if got != 0:
                state = got + state
            if int(state) > 10:
                state = 10
            await set_loop(chat_id, state)
            return await reply_note(message, 
                _["admin_25"].format(message.from_user.first_name, state)
            )
        else:
            return await reply_note(message, _["admin_26"])
    elif state.lower() == "enable":
        await set_loop(chat_id, 10)
        return await reply_note(message, 
            _["admin_25"].format(message.from_user.first_name, 10)
        )
    elif state.lower() == "disable":
        await set_loop(chat_id, 0)
        return await reply_note(message, _["admin_27"])
    else:
        return await reply_note(message, usage)
