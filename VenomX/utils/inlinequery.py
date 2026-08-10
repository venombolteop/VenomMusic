
# All rights reserved.

from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

answer = []

answer.extend(
    [
        InlineQueryResultArticle(
            title="ᴘᴀᴜsᴇ sᴛʀᴇᴀᴍ",
            description=f"ᴘᴀᴜsᴇ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴘʟᴀʏɪɴɢ sᴏɴɢ ᴏɴ ᴠᴏɪᴄᴇᴄʜᴀᴛ.",
            thumb_url="https://te.legra.ph/file/7345db59ab5d2c5cb142a.jpg",
            input_message_content=InputTextMessageContent("/pause"),
        ),
        InlineQueryResultArticle(
            title="ʀᴇsᴜᴍᴇ sᴛʀᴇᴀᴍ",
            description=f"ʀᴇsᴜᴍᴇ ᴛʜᴇ ᴘᴀᴜsᴇᴅ sᴏɴɢ ᴏɴ ᴠᴏɪᴄᴇᴄʜᴀᴛ.",
            thumb_url="https://te.legra.ph/file/9fe24bde84b1d31f685a9.jpg",
            input_message_content=InputTextMessageContent("/resume"),
        ),
        InlineQueryResultArticle(
            title="ᴍᴜᴛᴇ sᴛʀᴇᴀᴍ",
            description=f"ᴍᴜᴛᴇ ᴛʜᴇ ᴏɴɢᴏɪɴɢ sᴏɴɢ ᴏɴ ᴠᴏɪᴄᴇᴄʜᴀᴛ",
            thumb_url="https://te.legra.ph/file/c03f25028fa248401d519.jpg",
            input_message_content=InputTextMessageContent("/vcmute"),
        ),
        InlineQueryResultArticle(
            title="ᴜɴᴍᴜᴛᴇ sᴛʀᴇᴀᴍ",
            description=f"ᴜɴᴍᴜᴛᴇ ᴛʜᴇ ᴏɴɢᴏɪɴɢ sᴏɴɢ ᴏɴ ᴠᴏɪᴄᴇᴄʜᴀᴛ",
            thumb_url="https://te.legra.ph/file/98622051acad1988886be.jpg",
            input_message_content=InputTextMessageContent("/vcunmute"),
        ),
        InlineQueryResultArticle(
            title="sᴋɪᴘ sᴛʀᴇᴀᴍ",
            description=f"sᴋɪᴘ ᴛᴏ ɴᴇxᴛ ᴛʀᴀᴄᴋ. | sᴋɪᴘ ᴛᴏ ɴᴇxᴛ ᴛʀᴀᴄᴋ. | ғᴏʀ sᴘᴇᴄɪғɪᴄ ᴛʀᴀᴄᴋ ɴᴜᴍʙᴇʀ: /skip [number] ",
            thumb_url="https://te.legra.ph/file/1b78431fe8de0e497c188.jpg",
            input_message_content=InputTextMessageContent("/skip"),
        ),
        InlineQueryResultArticle(
            title="ᴇɴᴅ sᴛʀᴇᴀᴍ",
            description="sᴛᴏᴘ ᴛʜᴇ ᴏɴɢᴏɪɴɢ sᴏɴɢ ᴏɴ ɢʀᴏᴜᴘ ᴠᴏɪᴄᴇᴄʜᴀᴛ.",
            thumb_url="https://te.legra.ph/file/d3663021fb51e14a84aa9.jpg",
            input_message_content=InputTextMessageContent("/stop"),
        ),
        InlineQueryResultArticle(
            title="sʜᴜғғʟᴇ sᴛʀᴇᴀᴍ",
            description="sʜᴜғғʟᴇ ᴛʜᴇ ǫᴜᴇᴜᴇᴅ ᴛʀᴀᴄᴋs ʟɪsᴛ.",
            thumb_url="https://te.legra.ph/file/3d130381bf5945c139023.jpg",
            input_message_content=InputTextMessageContent("/shuffle"),
        ),
        InlineQueryResultArticle(
            title="sᴇᴇᴋ sᴛʀᴇᴀᴍ",
            description="sᴇᴇᴋ ᴛʜᴇ ᴏɴɢᴏɪɴɢ sᴛʀᴇᴀᴍ ᴛᴏ ᴀ sᴘᴇᴄɪғɪᴄ ᴅᴜʀᴀᴛɪᴏɴ.",
            thumb_url="https://te.legra.ph/file/c66abbf490158487fdb72.jpg",
            input_message_content=InputTextMessageContent("/seek 10"),
        ),
        InlineQueryResultArticle(
            title="ʟᴏᴏᴘ sᴛʀᴇᴀᴍ",
            description="ʟᴏᴏᴘ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴘʟᴀʏɪɴɢ ᴍᴜsɪᴄ. ᴜsᴀsɢᴇ: /loop [enable|disable]",
            thumb_url="https://te.legra.ph/file/f739e6067725fa88ce8d3.jpg",
            input_message_content=InputTextMessageContent("/loop 3"),
        ),
    ]
)
