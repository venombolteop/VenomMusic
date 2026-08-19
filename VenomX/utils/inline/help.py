
# All rights reserved.
#
from pyrogram.types import InlineKeyboardMarkup

from config import SUPPORT_GROUP
from VenomX import app
from VenomX.utils.premium import (
    back_btn,
    close_btn,
    link_btn,
)


def support_group_markup(_):
    upl = InlineKeyboardMarkup(
        [
            [
                link_btn(
                    _["S_B_3"],
                    url=SUPPORT_GROUP,
                    emoji="📱",
                ),
            ]
        ]
    )
    return upl


def help_back_markup(_):
    upl = InlineKeyboardMarkup(
        [
            [
                back_btn(
                    _["BACK_BUTTON"], "settings_back_helper"
                ),
                close_btn(_["CLOSE_BUTTON"]),
            ]
        ]
    )
    return upl


def private_help_panel(_):
    buttons = [
        [
            link_btn(
                _["S_B_1"], url=f"https://t.me/{app.username}?start=help", emoji="⭐"
            )
        ],
    ]
    return buttons
