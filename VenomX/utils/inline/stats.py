
# All rights reserved.
#
from pyrogram.types import InlineKeyboardMarkup

from VenomX import app
from VenomX.utils.premium import (
    back_btn,
    close_btn,
    fire_btn,
    link_btn,
    music_btn,
    _btn,
)
from pyrogram.enums import ButtonStyle


def back_stats_markup(_):
    upl = InlineKeyboardMarkup(
        [
            [
                back_btn(
                    _["BACK_BUTTON"],
                    "TOPMARKUPGET",
                ),
                close_btn(
                    _["CLOSE_BUTTON"],
                ),
            ],
        ]
    )
    return upl


def overallback_stats_markup(_):
    upl = InlineKeyboardMarkup(
        [
            [
                back_btn(
                    _["BACK_BUTTON"],
                    "GlobalStats",
                ),
                close_btn(
                    _["CLOSE_BUTTON"],
                ),
            ],
        ]
    )
    return upl


def get_stats_markup(_, status):
    not_sudo = [
        close_btn(
            _["CLOSEMENU_BUTTON"],
        )
    ]
    sudo = [
        fire_btn(
            _["SA_B_8"],
            "bot_stats_sudo g",
        ),
        close_btn(
            _["CLOSEMENU_BUTTON"],
        ),
    ]
    upl = InlineKeyboardMarkup(
        [
            [
                fire_btn(
                    _["SA_B_7"],
                    "TOPMARKUPGET",
                )
            ],
            [
                link_btn(
                    _["SA_B_6"],
                    url=f"https://t.me/{app.username}?start=stats",
                ),
                fire_btn(
                    _["SA_B_5"],
                    "TopOverall g",
                ),
            ],
            sudo if status else not_sudo,
        ]
    )
    return upl


def stats_buttons(_, status):
    not_sudo = [
        fire_btn(
            _["SA_B_5"],
            "TopOverall s",
        )
    ]
    sudo = [
        fire_btn(
            _["SA_B_8"],
            "bot_stats_sudo s",
        ),
        fire_btn(
            _["SA_B_5"],
            "TopOverall s",
        ),
    ]
    upl = InlineKeyboardMarkup(
        [
            sudo if status else not_sudo,
            [
                close_btn(
                    _["CLOSE_BUTTON"],
                ),
            ],
        ]
    )
    return upl


def back_stats_buttons(_):
    upl = InlineKeyboardMarkup(
        [
            [
                back_btn(
                    _["BACK_BUTTON"],
                    "GETSTATS",
                ),
                close_btn(
                    _["CLOSE_BUTTON"],
                ),
            ],
        ]
    )
    return upl


def top_ten_stats_markup(_):
    upl = InlineKeyboardMarkup(
        [
            [
                fire_btn(
                    _["SA_B_2"],
                    "GetStatsNow Tracks",
                ),
                fire_btn(
                    _["SA_B_1"],
                    "GetStatsNow Chats",
                ),
            ],
            [
                fire_btn(
                    _["SA_B_3"],
                    "GetStatsNow Users",
                ),
                fire_btn(
                    _["SA_B_4"],
                    "GetStatsNow Here",
                ),
            ],
            [
                back_btn(
                    _["BACK_BUTTON"],
                    "GlobalStats",
                ),
                close_btn(
                    _["CLOSE_BUTTON"],
                ),
            ],
        ]
    )
    return upl
