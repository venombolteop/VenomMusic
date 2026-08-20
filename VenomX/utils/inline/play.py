
# All rights reserved.
#

import math

from pyrogram.types import InlineKeyboardButton

from VenomX.utils.formatters import time_to_seconds
from VenomX.utils.premium import (
    back_btn,
    close_btn,
    loop_btn,
    music_btn,
    mute_btn,
    nav_btn,
    pause_btn,
    play_btn,
    seek_btn,
    shuffle_btn,
    skip_btn,
    stop_btn,
    unmute_btn,
    video_btn,
    _btn,
)
from pyrogram.enums import ButtonStyle


def get_progress_bar(percentage):
    umm = math.floor(percentage)

    if 0 < umm <= 10:
        return "▰▱▱▱▱▱▱▱▱"
    elif 10 < umm <= 20:
        return "▰▰▱▱▱▱▱▱▱"
    elif 20 < umm <= 30:
        return "▰▰▰▱▱▱▱▱▱"
    elif 30 < umm <= 40:
        return "▰▰▰▰▱▱▱▱▱"
    elif 40 < umm <= 50:
        return "▰▰▰▰▰▱▱▱▱"
    elif 50 < umm <= 60:
        return "▰▰▰▰▰▰▱▱▱"
    elif 60 < umm <= 70:
            return "▰▰▰▰▰▰▰▱▱"
    elif 70 < umm <= 80:
        return "▰▰▰▰▰▰▰▰▱"
    elif 80 < umm <= 90:
        return "▰▰▰▰▰▰▰▰▰"
    elif 90 < umm <= 100:
        return "▰▰▰▰▰▰▰▰▰▰"
    else:
        return "▱▱▱▱▱▱▱▱▱"


def stream_markup_timer(_, videoid, chat_id, played, dur):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    percentage = (played_sec / duration_sec) * 100

    bar = get_progress_bar(percentage)

    buttons = [
        [
            _btn(
                f"{played} {bar} {dur}",
                callback_data="GetTimer",
                style=ButtonStyle.PRIMARY,
                emoji="🌟",
            )
        ],
        [
            music_btn(_["P_B_7"], f"add_playlist {videoid}"),
            music_btn(_["PL_B_3"], f"PanelMarkup {videoid}|{chat_id}"),
        ],
        [
            play_btn("Resume", f"ADMIN Resume|{chat_id}"),
            pause_btn("Pause", f"ADMIN Pause|{chat_id}"),
            skip_btn("Skip", f"ADMIN Skip|{chat_id}"),
            stop_btn("Stop", f"ADMIN Stop|{chat_id}"),
        ],
        [close_btn(_["CLOSEMENU_BUTTON"])],
    ]
    return buttons


def stream_markup(_, videoid, chat_id):
    buttons = [
        [
            music_btn(_["P_B_7"], f"add_playlist {videoid}"),
            music_btn(_["PL_B_3"], f"PanelMarkup None|{chat_id}"),
        ],
        [
            play_btn("Resume", f"ADMIN Resume|{chat_id}"),
            pause_btn("Pause", f"ADMIN Pause|{chat_id}"),
            skip_btn("Skip", f"ADMIN Skip|{chat_id}"),
            stop_btn("Stop", f"ADMIN Stop|{chat_id}"),
        ],
        [close_btn(_["CLOSEMENU_BUTTON"])],
    ]
    return buttons


def telegram_markup_timer(_, chat_id, played, dur):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    percentage = (played_sec / duration_sec) * 100

    bar = get_progress_bar(percentage)

    buttons = [
        [
            _btn(
                f"{played} {bar} {dur}",
                callback_data="GetTimer",
                style=ButtonStyle.PRIMARY,
                emoji="🌟",
            )
        ],
        [
            music_btn(_["PL_B_3"], f"PanelMarkup None|{chat_id}"),
        ],
        [
            play_btn("Resume", f"ADMIN Resume|{chat_id}"),
            pause_btn("Pause", f"ADMIN Pause|{chat_id}"),
            skip_btn("Skip", f"ADMIN Skip|{chat_id}"),
            stop_btn("Stop", f"ADMIN Stop|{chat_id}"),
        ],
        [
            close_btn(_["CLOSEMENU_BUTTON"]),
        ],
    ]
    return buttons


def telegram_markup(_, chat_id):
    buttons = [
        [
            music_btn(_["PL_B_3"], f"PanelMarkup None|{chat_id}"),
        ],
        [
            play_btn("Resume", f"ADMIN Resume|{chat_id}"),
            pause_btn("Pause", f"ADMIN Pause|{chat_id}"),
            skip_btn("Skip", f"ADMIN Skip|{chat_id}"),
            stop_btn("Stop", f"ADMIN Stop|{chat_id}"),
        ],
        [
            close_btn(_["CLOSEMENU_BUTTON"]),
        ],
    ]
    return buttons


## Search Query Inline


def track_markup(_, videoid, user_id, channel, fplay):
    buttons = [
        [
            music_btn(
                _["P_B_1"],
                f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            video_btn(
                _["P_B_2"],
                f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            close_btn(
                _["CLOSE_BUTTON"], f"forceclose {videoid}|{user_id}"
            )
        ],
    ]
    return buttons


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            music_btn(
                _["P_B_1"],
                f"AyushPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}",
            ),
            video_btn(
                _["P_B_2"],
                f"AyushPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}",
            ),
        ],
        [
            close_btn(
                _["CLOSE_BUTTON"], f"forceclose {videoid}|{user_id}"
            ),
        ],
    ]
    return buttons


## Live Stream Markup


def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    buttons = [
        [
            play_btn(
                _["P_B_3"],
                f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
            ),
            close_btn(
                _["CLOSEMENU_BUTTON"],
                f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


## Slider Query Markup


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    query = f"{query[:20]}"
    buttons = [
        [
            music_btn(
                _["P_B_1"],
                f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            video_btn(
                _["P_B_2"],
                f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            nav_btn(
                "Prev",
                f"slider B|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
            close_btn(
                _["CLOSE_BUTTON"], f"forceclose {query}|{user_id}"
            ),
            nav_btn(
                "Next",
                f"slider F|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
        ],
    ]
    return buttons


def panel_markup_1(_, videoid, chat_id):
    buttons = [
        [
            pause_btn(
                "Pause", f"ADMIN Pause|{chat_id}"
            ),
            play_btn(
                "Resume",
                f"ADMIN Resume|{chat_id}",
            ),
        ],
        [
            skip_btn("Skip", f"ADMIN Skip|{chat_id}"),
            stop_btn("Stop", f"ADMIN Stop|{chat_id}"),
        ],
        [
            loop_btn(
                "Replay", f"ADMIN Replay|{chat_id}"
            ),
        ],
        [
            nav_btn(
                "Prev",
                f"Pages Back|0|{videoid}|{chat_id}",
            ),
            back_btn(
                "Back",
                f"MainMarkup {videoid}|{chat_id}",
            ),
            nav_btn(
                "Next",
                f"Pages Forw|0|{videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons


def panel_markup_2(_, videoid, chat_id):
    buttons = [
        [
            mute_btn("Mute", f"ADMIN Mute|{chat_id}"),
            unmute_btn(
                "Unmute",
                f"ADMIN Unmute|{chat_id}",
            ),
        ],
        [
            shuffle_btn(
                "Shuffle",
                f"ADMIN Shuffle|{chat_id}",
            ),
            loop_btn("Loop", f"ADMIN Loop|{chat_id}"),
        ],
        [
            nav_btn(
                "Prev",
                f"Pages Back|1|{videoid}|{chat_id}",
            ),
            back_btn(
                "Back",
                f"MainMarkup {videoid}|{chat_id}",
            ),
            nav_btn(
                "Next",
                f"Pages Forw|1|{videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons


def panel_markup_3(_, videoid, chat_id):
    buttons = [
        [
            seek_btn(
                "10s Back",
                f"ADMIN 1|{chat_id}",
            ),
            seek_btn(
                "10s Forward",
                f"ADMIN 2|{chat_id}",
            ),
        ],
        [
            seek_btn(
                "30s Back",
                f"ADMIN 3|{chat_id}",
            ),
            seek_btn(
                "30s Forward",
                f"ADMIN 4|{chat_id}",
            ),
        ],
        [
            nav_btn(
                "Prev",
                f"Pages Back|2|{videoid}|{chat_id}",
            ),
            back_btn(
                "Back",
                f"MainMarkup {videoid}|{chat_id}",
            ),
            nav_btn(
                "Next",
                f"Pages Forw|2|{videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons
