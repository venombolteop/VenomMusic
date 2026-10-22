
# All rights reserved.
#



import asyncio
import sys
from pathlib import Path

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)

import uvloop

uvloop.install()

import config

from ..logging import LOGGER


def _package_version(distribution: str) -> str:
    """An installed package's version, read rather than written into the banner.

    The banner line is labelled py-tgcalls, so it reports py-tgcalls. It once
    reported the bot's own version instead — a different thing wearing this
    label, and wrong in the way that reads as authoritative, because the banner
    has always been where you look when something behaves as the wrong version.

    Falls back to "unknown" rather than a plausible-looking guess. Being
    confidently wrong on this line costs more than it being unhelpful.
    """
    try:
        from importlib.metadata import version
        return str(version(distribution))
    except Exception:
        return "unknown"




_BOT_SESSION_FILE = Path("cache/bot_session.str")


class AyuBot(Client):
    def __init__(self):
        LOGGER(__name__).info(f"Starting Bot")
        # A stored session string means a restart never touches
        # auth.ImportBotAuthorization again — fresh bot logins flood-wait hard.
        session_string = None
        try:
            if _BOT_SESSION_FILE.exists():
                session_string = _BOT_SESSION_FILE.read_text().strip() or None
        except Exception:
            session_string = None
        super().__init__(
            "VenomX",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            session_string=session_string,
            in_memory=True,
        )

    async def start(self):
        from pyrogram.errors import FloodWait

        for _attempt in range(12):
            try:
                await super().start()
                break
            except FloodWait as e:
                wait = int(e.value) + 5
                LOGGER(__name__).warning(
                    "Bot auth flood-wait %ss — sleeping, will retry", wait
                )
                await asyncio.sleep(wait)
        else:
            raise RuntimeError("Bot login kept flood-waiting; giving up")
        try:
            if not _BOT_SESSION_FILE.exists():
                _BOT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
                _BOT_SESSION_FILE.write_text(await self.export_session_string())
        except Exception:
            pass
        get_me = await self.get_me()
        self.username = get_me.username
        self.id = get_me.id
        self.name = self.me.first_name + " " + (self.me.last_name or "")
        self.mention = self.me.mention

        try:
            # Reported, not asserted. The point of a startup banner is to be the
            # one place you look when something later behaves as the wrong
            # version, so both are read from the host rather than written into the
            # text. "3.x" and a pinned "v2.3.3" are both claims nobody re-checks,
            # which is how a Python 3.11 host ends up advertising 3.x.
            python_version = "%d.%d.%d" % sys.version_info[:3]
            tgcalls_version = _package_version("py-tgcalls")
            start_msg = f"""
╔══════════╗
  🎵 **{self.mention}** 🎵
╚══════════╝

⚡ **ʙᴏᴛ sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ**

┌────────────┐
│ 🔑 **ɪᴅ :** <code>{self.id}</code>
│ 🧑 **ɴᴀᴍᴇ :** {self.name}
│ 🔗 **ᴜsᴇʀɴᴀᴍᴇ :** @{self.username}
│ 📡 **ʜᴜɴᴛᴇʀ :** {config.OWNER_ID[0]}
│ 🌐 **ᴘʟᴀᴛғᴏʀᴍ :** ᴄʟᴏᴜᴅ ʟɪɴᴜx
│ 🐍 **ᴘʏᴛʜᴏɴ :** {python_version}
│ ⚙️ **ᴘʏᴛɢᴄᴀʟʟs :** v{tgcalls_version}
└────────────┘

🚀 **ʀᴇᴀᴅʏ ᴛᴏ ᴘʟᴀʏ ᴍᴜsɪᴄ**
💎 **ᴘʀᴇᴍɪᴜᴍ ᴜɪ ᴀᴄᴛɪᴠᴇ**
🔥 **ᴠᴏɪᴄᴇᴄʜᴀᴛ ᴄᴏɴɴᴇᴄᴛᴇᴅ**
"""
            await self.send_message(
                config.LOGGER_ID,
                text=start_msg,
            )
        except:
            LOGGER(__name__).error(
                "Bot has failed to access the log Group. Make sure that you have added your bot to your log channel and promoted as admin!"
            )
            # sys.exit()
        if config.SET_CMDS == str(True):
            try:

                await self.set_bot_commands(
                    commands=[
                        BotCommand("start", "sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
                        BotCommand("help", "ɢᴇᴛ ᴛʜᴇ ʜᴇʟᴘ ᴍᴇɴᴜ"),
                        BotCommand("ping", "ᴄʜᴇᴄᴋ ʙᴏᴛ ɪs ᴀʟɪᴠᴇ ᴏʀ ᴅᴇᴀᴅ"),
                    ],
                    scope=BotCommandScopeAllPrivateChats(),
                )
                await self.set_bot_commands(
                    commands=[
                        BotCommand("play", "sᴛᴀʀᴛ ᴘʟᴀʏɪɴɢ ʀᴇǫᴜᴇsᴛᴇᴅ sᴏɴɢ"),
                    ],
                    scope=BotCommandScopeAllGroupChats(),
                )
                await self.set_bot_commands(
                    commands=[
                        BotCommand("play", "sᴛᴀʀᴛ ᴘʟᴀʏɪɴɢ ʀᴇǫᴜᴇsᴛᴇᴅ sᴏɴɢ"),
                        BotCommand("skip", "ᴍᴏᴠᴇ ᴛᴏ ɴᴇxᴛ ᴛʀᴀᴄᴋ ɪɴ ǫᴜᴇᴜᴇ"),
                        BotCommand("pause", "ᴘᴀᴜsᴇ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴘʟᴀʏɪɴɢ sᴏɴɢ"),
                        BotCommand("resume", "ʀᴇsᴜᴍᴇ ᴛʜᴇ ᴘᴀᴜsᴇᴅ sᴏɴɢ"),
                        BotCommand("end", "ᴄʟᴇᴀʀ ᴛʜᴇ ǫᴜᴇᴜᴇ ᴀᴍᴅ ʟᴇᴀᴠᴇ ᴠᴏɪᴄᴇᴄʜᴀᴛ"),
                        BotCommand("shuffle", "ʀᴀɴᴅᴏᴍʟʏ sʜᴜғғʟᴇs ᴛʜᴇ ǫᴜᴇᴜᴇᴅ ᴘʟᴀʏʟɪsᴛ."),
                        BotCommand(
                            "playmode",
                            "ᴀʟʟᴏᴡs ʏᴏᴜ ᴛᴏ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴅᴇғᴀᴜʟᴛ ᴘʟᴀʏᴍᴏᴅᴇ ғᴏʀ ʏᴏᴜʀ ᴄʜᴀᴛ",
                        ),
                        BotCommand(
                            "settings",
                            "Oᴘᴇɴ ᴛʜᴇ sᴇᴛᴛɪɴɢs ᴏғ ᴛʜᴇ ᴍᴜsɪᴄ ʙᴏᴛ ғᴏʀ ʏᴏᴜʀ ᴄʜᴀᴛ.",
                        ),
                    ],
                    scope=BotCommandScopeAllChatAdministrators(),
                )
            except:
                pass
        else:
            pass
        try:
            a = await self.get_chat_member(config.LOGGER_ID, self.id)
            if a.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error("Please promote Bot as Admin in Logger Group")
                sys.exit()
        except Exception:
            pass
        if get_me.last_name:
            self.name = get_me.first_name + " " + get_me.last_name
        else:
            self.name = get_me.first_name
        LOGGER(__name__).info(f"MusicBot Started as {self.name}")
