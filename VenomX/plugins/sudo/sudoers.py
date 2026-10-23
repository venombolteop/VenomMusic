
# All rights reserved.
#

from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS, MONGO_DB_URI, OWNER_ID
from strings import command
from VenomX import app
from VenomX.misc import SUDOERS
from VenomX.utils.database import add_sudo, remove_sudo
from VenomX.utils.decorators.language import language
from VenomX.utils.rich_msg import reply_note, status_card


@app.on_message(command("ADDSUDO_COMMAND") & filters.user(OWNER_ID))
@language
async def useradd(client, message: Message, _):
    if not MONGO_DB_URI:
        return await reply_note(message, 
            "**Due to privacy issues, You can't manage sudoers when you are on Venom Database.\n\n Please fill Your MONGO_DB_URI in your vars to use this features**"
        )
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await reply_note(message, _["general_1"])
        user = message.text.split(None, 1)[1]
        if "@" in user:
            user = user.replace("@", "")
        user = await app.get_users(user)
        if user.id in SUDOERS:
            return await reply_note(message, _["sudo_1"].format(user.mention))
        added = await add_sudo(user.id)
        if added:
            SUDOERS.add(user.id)
            await reply_note(message, _["sudo_2"].format(user.mention))
        else:
            await reply_note(message, "Something wrong happened")
        return
    if message.reply_to_message.from_user.id in SUDOERS:
        return await reply_note(message, 
            _["sudo_1"].format(message.reply_to_message.from_user.mention)
        )
    added = await add_sudo(message.reply_to_message.from_user.id)
    if added:
        SUDOERS.add(message.reply_to_message.from_user.id)
        await reply_note(message, 
            _["sudo_2"].format(message.reply_to_message.from_user.mention)
        )
    else:
        await reply_note(message, "Something wrong happened")
    return


@app.on_message(command("DELSUDO_COMMAND") & filters.user(OWNER_ID))
@language
async def userdel(client, message: Message, _):
    if not MONGO_DB_URI:
        return await reply_note(message, 
            "**Due to privacy issues, You can't manage sudoers when you are on Venom Database.\n\n Please fill Your MONGO_DB_URI in your vars to use this features**"
        )
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await reply_note(message, _["general_1"])
        user = message.text.split(None, 1)[1]
        if "@" in user:
            user = user.replace("@", "")
        user = await app.get_users(user)
        if user.id not in SUDOERS:
            return await reply_note(message, _["sudo_3"])
        removed = await remove_sudo(user.id)
        if removed:
            SUDOERS.remove(user.id)
            await reply_note(message, _["sudo_4"])
            return
        await reply_note(message, f"Something wrong happened")
        return
    user_id = message.reply_to_message.from_user.id
    if user_id not in SUDOERS:
        return await reply_note(message, _["sudo_3"])
    removed = await remove_sudo(user_id)
    if removed:
        SUDOERS.remove(user_id)
        await reply_note(message, _["sudo_4"])
        return
    await reply_note(message, f"Something wrong happened")


@app.on_message(command("SUDOUSERS_COMMAND") & ~BANNED_USERS)
@language
async def sudoers_list(client, message: Message, _):
    text = _["sudo_5"]
    count = 0
    for x in OWNER_ID:
        try:
            user = await app.get_users(x)
            user = user.first_name if not user.mention else user.mention
            count += 1
        except Exception:
            continue
        text += f"{count}➤ {user} (`{x}`)\n"
    smex = 0
    for user_id in SUDOERS:
        if user_id not in OWNER_ID:
            try:
                user = await app.get_users(user_id)
                user = user.first_name if not user.mention else user.mention
                if smex == 0:
                    smex += 1
                    text += _["sudo_6"]
                count += 1
                text += f"{count}➤ {user} (`{user_id}`)\n"
            except Exception:
                continue
    if not text:
        await reply_note(message, _["sudo_7"])
    else:
        await reply_note(message, text)
