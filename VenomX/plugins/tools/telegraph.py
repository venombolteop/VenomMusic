#code by @K_4ip Telegram channel :- @VenomOwners
# don't remove credit 

import requests
from pyrogram import Client, filters
from VenomX import app
from config import API_KEY



# Function to upload media (image, video, gif) to ImgBB without API key
def upload_media_to_imgbb(media_path):
    url = "https://api.imgbb.com/1/upload"
    # This is a public anonymous key from ImgBB for basic usage (replace with yours if necessary)
    key = API_KEY # You can get one for free by registering
    
    with open(media_path, 'rb') as file:
        response = requests.post(url, data={'key': key}, files={'image': file})

    if response.status_code == 200:
        return response.json().get("data", {}).get("url", None)
    else:
        return None



@app.on_message(filters.command("tgm"))
async def link_media_handler(client, message):
    media_path = None

    # Check for media types
    if message.reply_to_message:
        if message.reply_to_message.photo:
            # Download the photo
            media_path = await message.reply_to_message.download()
        elif message.reply_to_message.video:
            # Download the video
            media_path = await message.reply_to_message.download()
        elif message.reply_to_message.document and message.reply_to_message.document.mime_type == 'image/gif':
            # Download the GIF (as document)
            media_path = await message.reply_to_message.download()
        elif message.reply_to_message.sticker:
            # Download the sticker
            media_path = await message.reply_to_message.download()

        if media_path:
            imgbb_link = upload_media_to_imgbb(media_path)
            
            if imgbb_link:
                # Send a message with the link embedded under text using Markdown format
                text = f"Here is your media: {imgbb_link}"
                await message.reply_text(text)
            else:
                await message.reply_text("Failed to upload the media.")
        else:
            await message.reply_text("Unsupported media type or no media found.")
    else:
        await message.reply_text("Please reply to a photo, video, GIF, or sticker.")


