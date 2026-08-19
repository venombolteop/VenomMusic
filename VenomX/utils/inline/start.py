
# All rights reserved.
#
from typing import Union

from config import GITHUB_REPO, SUPPORT_CHANNEL, SUPPORT_GROUP
from VenomX import app
from VenomX.utils.premium import (
    back_btn,
    close_btn,
    link_btn,
    settings_btn,
    _btn,
)
from pyrogram.enums import ButtonStyle


def start_pannel(_):
    buttons = [
        [
            link_btn(
                _["S_B_1"],
                url=f"https://t.me/{app.username}?start=help",
                emoji="⭐",
            ),
            settings_btn(_["S_B_2"], "settings_helper"),
        ],
    ]
    if SUPPORT_CHANNEL and SUPPORT_GROUP:
        buttons.append(
            [
                link_btn(_["S_B_4"], url=f"{SUPPORT_CHANNEL}", emoji="📱"),
                link_btn(_["S_B_3"], url=f"{SUPPORT_GROUP}", emoji="📱"),
            ]
        )
    else:
        if SUPPORT_CHANNEL:
            buttons.append(
                [link_btn(_["S_B_4"], url=f"{SUPPORT_CHANNEL}", emoji="📱")]
            )
        if SUPPORT_GROUP:
            buttons.append(
                [link_btn(_["S_B_3"], url=f"{SUPPORT_GROUP}", emoji="📱")]
            )
    return buttons


def private_panel(_, BOT_USERNAME, OWNER: Union[bool, int] = None):
    buttons = [
        [back_btn(_["S_B_8"], "settings_back_helper")]
    ]
    if SUPPORT_CHANNEL and SUPPORT_GROUP:
        buttons.append(
            [
                link_btn(_["S_B_4"], url=f"{SUPPORT_CHANNEL}", emoji="📱"),
                link_btn(_["S_B_3"], url=f"{SUPPORT_GROUP}", emoji="📱"),
            ]
        )
    else:
        if SUPPORT_CHANNEL:
            buttons.append(
                [link_btn(_["S_B_4"], url=f"{SUPPORT_CHANNEL}", emoji="📱")]
            )
        if SUPPORT_GROUP:
            buttons.append(
                [link_btn(_["S_B_3"], url=f"{SUPPORT_GROUP}", emoji="📱")]
            )
    buttons.append(
        [
            link_btn(_["S_B_5"], url=f"https://t.me/{BOT_USERNAME}?startgroup=true", emoji="✨")
        ]
    )
    if GITHUB_REPO and OWNER:
        buttons.append(
            [
                link_btn(_["S_B_7"], url=f"tg://user?id={OWNER}", emoji="📱"),
                link_btn(_["S_B_6"], url=f"{GITHUB_REPO}", emoji="💻"),
            ]
        )
    else:

        if GITHUB_REPO:
            buttons.append(
                [
                    link_btn(_["S_B_6"], url=f"{GITHUB_REPO}", emoji="💻"),
                ]
            )

        if OWNER:
            buttons.append(
                [
                    link_btn(_["S_B_7"], url=f"tg://user?id={OWNER}", emoji="📱"),
                ]
            )
    buttons.append([settings_btn(_["ST_B_6"], "LG")])
    return buttons
