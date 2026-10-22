import os
from pyrogram import filters
from VenomX import app
import requests
from VenomX.utils.rich_msg import (
    pemoji,
    rich_esc,
    rich_heading,
    rich_url_button,
    rich_button_row,
    send_rich,
)


def upload_file(file_path):
    url = "https://catbox.moe/user/api.php"
    data = {"reqtype": "fileupload", "json": "true"}
    files = {"fileToUpload": open(file_path, "rb")}
    response = requests.post(url, data=data, files=files)

    if response.status_code == 200:
        return True, response.text.strip()
    else:
        return False, f"ᴇʀʀᴏʀ: {response.status_code} - {response.text}"


@app.on_message(filters.command(["tgm", "tgt", "telegraph", "tl"]))
async def get_link_group(client, message):
    if not message.reply_to_message:
        return await message.reply_text(
            "Pʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇᴅɪᴀ ᴛᴏ ᴜᴘʟᴏᴀᴅ ᴏɴ Tᴇʟᴇɢʀᴀᴘʜ"
        )

    media = message.reply_to_message
    file_size = 0
    if media.photo:
        file_size = media.photo.file_size
    elif media.video:
        file_size = media.video.file_size
    elif media.document:
        file_size = media.document.file_size

    if file_size > 200 * 1024 * 1024:
        return await message.reply_text("⚠️ Pʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴍᴇᴅɪᴀ ꜰɪʟᴇ ᴜɴᴅᴇʀ 200MB.")

    try:
        text = await message.reply("Pʀᴏᴄᴇꜱꜱɪɴɢ...")

        async def progress(current, total):
            try:
                await text.edit_text(f"📥 Dᴏᴡɴʟᴏᴀᴅɪɴɢ... {current * 100 / total:.1f}%")
            except Exception:
                pass

        try:
            local_path = await media.download(progress=progress)
            await text.edit_text("📤 Uᴘʟᴏᴀᴅɪɴɢ ᴛᴏ ᴄᴀᴛʙᴏx...")

            success, upload_path = upload_file(local_path)

            if success:
                await text.delete()
                body = rich_heading(f'{pemoji("🌐")} ᴠᴇɴᴏᴍ ʟɪɴᴋ-ᴏ-ᴍᴀᴛɪᴄ', level=4)
                body += f"<p> uploader: <a href='{rich_esc(upload_path)}'>{rich_esc(upload_path)}</a></p>"
                body += rich_button_row(
                    rich_url_button("🌐 ᴄʀᴇᴀᴛᴇᴅ ʙʏ ᴠᴇɴᴏᴍ · ᴛᴀᴘ ᴛᴏ ꜱᴇᴇ", upload_path),
                )
                await send_rich(message.chat.id, body)
            else:
                await text.edit_text(
                    f"ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ ᴡʜɪʟᴇ ᴜᴘʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ꜰɪʟᴇ\n{upload_path}"
                )

            try:
                os.remove(local_path)
            except Exception:
                pass

        except Exception as e:
            await text.edit_text(f"❌ Fɪʟᴇ ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ\n\n<i>Rᴇᴀꜱᴏɴ: {e}</i>")
            try:
                os.remove(local_path)
            except Exception:
                pass
            return
    except Exception:
        pass
