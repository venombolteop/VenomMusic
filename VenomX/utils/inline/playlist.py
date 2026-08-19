
# All rights reserved.
#
from VenomX.utils.premium import (
    back_btn,
    close_btn,
    fire_btn,
    music_btn,
    settings_btn,
    star_btn,
    video_btn,
    _btn,
)
from pyrogram.enums import ButtonStyle


def botplaylist_markup(_):
    buttons = [
        [
            music_btn(_["PL_B_1"], "get_playlist_playmode"),
            star_btn(_["PL_B_8"], "get_top_playlists"),
        ],
        [
            settings_btn(_["PL_B_4"], "PM"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def top_play_markup(_):
    buttons = [
        [fire_btn(_["PL_B_9"], "SERVERTOP global")],
        [fire_btn(_["PL_B_10"], "SERVERTOP chat")],
        [fire_btn(_["PL_B_11"], "SERVERTOP user")],
        [
            back_btn(_["BACK_BUTTON"], "get_playmarkup"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def get_playlist_markup(_):
    buttons = [
        [
            music_btn(_["P_B_1"], "play_playlist a"),
            video_btn(_["P_B_2"], "play_playlist v"),
        ],
        [
            back_btn(_["BACK_BUTTON"], "home_play"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def top_play_markup(_):
    buttons = [
        [fire_btn(_["PL_B_9"], "SERVERTOP Global")],
        [fire_btn(_["PL_B_10"], "SERVERTOP Group")],
        [fire_btn(_["PL_B_11"], "SERVERTOP Personal")],
        [
            back_btn(_["BACK_BUTTON"], "get_playmarkup"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def failed_top_markup(_):
    buttons = [
        [
            back_btn(
                _["BACK_BUTTON"],
                "get_top_playlists",
            ),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def warning_markup(_):
    from pyrogram.types import InlineKeyboardMarkup
    upl = InlineKeyboardMarkup(
        [
            [
                _btn(
                    text=_["PL_B_7"],
                    callback_data="delete_whole_playlist",
                    style=ButtonStyle.DANGER,
                    emoji="🟠",
                ),
            ],
            [
                back_btn(
                    _["BACK_BUTTON"],
                    "del_back_playlist",
                ),
                close_btn(
                    _["CLOSE_BUTTON"],
                ),
            ],
        ]
    )
    return upl


def close_markup(_):
    from pyrogram.types import InlineKeyboardMarkup
    upl = InlineKeyboardMarkup(
        [
            [
                close_btn(
                    text=_["CLOSE_BUTTON"],
                ),
            ]
        ]
    )
    return upl
