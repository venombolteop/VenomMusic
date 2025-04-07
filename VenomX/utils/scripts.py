

import asyncio
import importlib
import math
import os
import re
import shlex
import subprocess
import sys
import time
import traceback
from io import BytesIO
from types import ModuleType
from typing import Dict, Tuple

import psutil
from PIL import Image
from pyrogram import Client, enums, errors
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import Message

META_COMMENTS = re.compile(r"^ *# *meta +(\S+) *: *(.*?)\s*$", re.MULTILINE)
interact_with_to_delete = []

def time_formatter(milliseconds: int) -> str:
    """Time Formatter"""
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + " day(s), ") if days else "")
        + ((str(hours) + " hour(s), ") if hours else "")
        + ((str(minutes) + " minute(s), ") if minutes else "")
        + ((str(seconds) + " second(s), ") if seconds else "")
        + ((str(milliseconds) + " millisecond(s), ") if milliseconds else "")
    )
    return tmp[:-2]


def humanbytes(size):
    """Convert Bytes To Bytes So That Human Can Read It"""
    if not size:
        return ""
    power = 2**10
    raised_to_pow = 0
    dict_power_n = {0: "", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    while size > power:
        size /= power
        raised_to_pow += 1
    return str(round(size, 2)) + " " + dict_power_n[raised_to_pow] + "B"


async def edit_or_send_as_file(
    tex: str,
    message: Message,
    client: Client,
    caption: str = "<code>Result!</code>",
    file_name: str = "result",
):
    """Send As File If Len Of Text Exceeds Tg Limit Else Edit Message"""
    if not tex:
        await message.edit("<code>Wait, What?</code>")
        return
    if len(tex) > 1024:
        await message.edit("<code>OutPut is Too Large, Sending As File!</code>")
        file_names = f"{file_name}.txt"
        with open(file_names, "w") as fn:
            fn.write(tex)
        await client.send_document(message.chat.id, file_names, caption=caption)
        await message.delete()
        if os.path.exists(file_names):
            os.remove(file_names)
        return
    return await message.edit(tex)


def get_text(message: Message) -> None | str:
    """Extract Text From Commands"""
    text_to_return = message.text
    if message.text is None:
        return None
    if " " in text_to_return:
        try:
            return message.text.split(None, 1)[1]
        except IndexError:
            return None
    else:
        return None


async def progress(current, total, message, start, type_of_ps, file_name=None):
    """Progress Bar For Showing Progress While Uploading / Downloading File - Normal"""
    now = time.time()
    diff = now - start
    if round(diff % 10.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        if elapsed_time == 0:
            return
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion
        progress_str = f"{''.join(['▰' for i in range(math.floor(percentage / 10))])}"
        progress_str += (
            f"{''.join(['▱' for i in range(10 - math.floor(percentage / 10))])}"
            )
        progress_str += f"{round(percentage, 2)}%\n"
        tmp = f"{progress_str}{humanbytes(current)} of {humanbytes(total)}\n"
        tmp += f"ETA: {time_formatter(estimated_total_time)}"
        if file_name:
            try:
                await message.edit(
                    f"{type_of_ps}\n**File Name:** `{file_name}`\n{tmp}"
                    )
            except FloodWait as e:
                await asyncio.sleep(e.x)
            except MessageNotModified:
                pass
        else:
            try:
                await message.edit(
                    f"{type_of_ps}\n{tmp}", parse_mode=enums.ParseMode.MARKDOWN
                    )
            except FloodWait as e:
                await asyncio.sleep(e.x)
            except MessageNotModified:
                pass


async def run_cmd(prefix: str) -> Tuple[str, str, int, int]:
    """Run Commands"""
    args = shlex.split(prefix)
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    stdout, stderr = await process.communicate()
    return (
        stdout.decode("utf-8", "replace").strip(),
        stderr.decode("utf-8", "replace").strip(),
        process.returncode,
        process.pid,
        )


def mediainfo(media):
    xx = str((str(media)).split("(", maxsplit=1)[0])
    m = ""
    if xx == "MessageMediaDocument":
        mim = media.document.mime_type
        if mim == "application/x-tgsticker":
            m = "sticker animated"
        elif "image" in mim:
            if mim == "image/webp":
                m = "sticker"
            elif mim == "image/gif":
                m = "gif as doc"
            else:
                m = "pic as doc"
        elif "video" in mim:
            if "DocumentAttributeAnimated" in str(media):
                m = "gif"
            elif "DocumentAttributeVideo" in str(media):
                i = str(media.document.attributes[0])
                if "supports_streaming=True" in i:
                    m = "video"
                m = "video as doc"
            else:
                m = "video"
        elif "audio" in mim:
            m = "audio"
        else:
            m = "document"
    elif xx == "MessageMediaPhoto":
        m = "pic"
    elif xx == "MessageMediaWebPage":
        m = "web"
    return m


async def edit_or_reply(message, txt):
    """Edit Message If Its From Self, Else Reply To Message"""
    if not message:
        return await message.edit(txt)
    if not message.from_user:
        return await message.edit(txt)
    return await message.edit(txt)


def format_exc(e: Exception, suffix="") -> str:
    traceback.print_exc()
    err = traceback.format_exc()
    if isinstance(e, errors.RPCError):
        return (
            f"<b>Telegram API error!</b>\n"
            f"<code>[{e.CODE} {e.ID or e.NAME}] — {e.MESSAGE.format(value=e.value)}</code>\n\n<b>{suffix}</b>"
            )
    return f"<b>Error!</b>\n" f"<code>{err}</code>"


def import_library(library_name: str, package_name: str = None):
    """
    Loads a library, or installs it in ImportError case
    :param library_name: library name (import example...)
    :param package_name: package name in PyPi (pip install example)
    :return: loaded module
    """
    if package_name is None:
        package_name = library_name
    requirements_list.append(package_name)

    try:
        return importlib.import_module(library_name)
    except ImportError as exc:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", package_name], check=True)
        if completed.returncode != 0:
            raise AssertionError(
                f"Failed to install library {package_name} (pip exited with code {completed.returncode})"
                ) from exc
        return importlib.import_module(library_name)


def uninstall_library(package_name: str):
    """
    Uninstalls a library
    :param package_name: package name in PyPi (pip uninstall example)
    """
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", package_name], check=True)
    if completed.returncode != 0:
        raise AssertionError(
            f"Failed to uninstall library {package_name} (pip exited with code {completed.returncode})"
        )


def resize_image(
    input_img, output=None, img_type="PNG", size: int = 512, size2: int = None
):
    if output is None:
        output = BytesIO()
        output.name = f"sticker.{img_type.lower()}"

    with Image.open(input_img) as img:
        # We used to use thumbnail(size) here, but it returns with a *max* dimension of 512,512
        # rather than making one side exactly 512, so we have to calculate dimensions manually :(
        if size2 is not None:
            size = (size, size2)
        elif img.width == img.height:
            size = (size, size)
        elif img.width < img.height:
            size = (max(size * img.width // img.height, 1), size)
        else:
            size = (size, max(size * img.height // img.width, 1))

        img.resize(size).save(output, img_type)

    return output


def resize_new_image(image_path, output_path, desired_width=None, desired_height=None):
    """
    Resize an image to the desired dimensions while maintaining the aspect ratio.

    Args:
        image_path (str): Path to the input image file.
        output_path (str): Path to save the resized image.
        desired_width (int, optional): Desired width in pixels. If not provided, the aspect ratio will be maintained.
        desired_height (int, optional): Desired height in pixels. If not provided, the aspect ratio will be maintained.
    """
    image = Image.open(image_path)

    width, height = image.size

    aspect_ratio = width / height

    if desired_width and desired_height:
        new_width, new_height = desired_width, desired_height
    elif desired_height:
        new_width, new_height = int(desired_height * aspect_ratio), desired_height
    else:
        new_width, new_height = 150, 150

    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    resized_image.save(output_path)
    if os.path.exists(image_path):
        os.remove(image_path)


def parse_meta_comments(code: str) -> Dict[str, str]:
    try:
        groups = META_COMMENTS.search(code).groups()
    except AttributeError:
        return {}

    return {groups[i]: groups[i + 1] for i in range(0, len(groups), 2)}


def ReplyCheck(message: Message):
    reply_id = None

    if message.reply_to_message:
        reply_id = message.reply_to_message.id

    elif not message.from_user.is_self:
        reply_id = message.id

    return reply_id
