
#
# All rights reserved.
#
from typing import Union

from pyrogram.types import InlineKeyboardMarkup

from VenomX.utils.premium import (
    back_btn,
    close_btn,
    music_btn,
    _btn,
)
from pyrogram.enums import ButtonStyle


def queue_markup(
    _,
    DURATION,
    CPLAY,
    videoid,
    played: Union[bool, int] = None,
    dur: Union[bool, int] = None,
):
    not_dur = [
        [
            music_btn(
                _["QU_B_1"],
                f"GetQueued {CPLAY}|{videoid}",
            ),
            close_btn(
                _["CLOSEMENU_BUTTON"],
            ),
        ]
    ]
    dur = [
        [
            _btn(
                text=_["QU_B_2"].format(played, dur),
                callback_data="GetTimer",
                style=ButtonStyle.PRIMARY,
                emoji="🌟",
            )
        ],
        [
            music_btn(
                _["QU_B_1"],
                f"GetQueued {CPLAY}|{videoid}",
            ),
            close_btn(
                _["CLOSEMENU_BUTTON"],
            ),
        ],
    ]
    upl = InlineKeyboardMarkup(not_dur if DURATION == "Unknown" else dur)
    return upl


def queue_back_markup(_, CPLAY):
    upl = InlineKeyboardMarkup(
        [
            [
                back_btn(
                    _["BACK_BUTTON"],
                    f"queue_back_timer {CPLAY}",
                ),
                close_btn(
                    _["CLOSE_BUTTON"],
                ),
            ]
        ]
    )
    return upl
