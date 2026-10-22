
# All rights reserved.
#
# Rich-message playlist markups (Bot API 10.3) — returns HTML fragments.
# Callback_data strings identical to the old inline buttons.

from VenomX.utils.rich_msg import (
    pemoji,
    rich_button,
    rich_button_row,
)


def botplaylist_markup(_):
    return (
        rich_button_row(
            rich_button(f"{pemoji('🎵')} {_['PL_B_1']}", callback_data="get_playlist_playmode", style="primary"),
            rich_button(f"{pemoji('⭐')} {_['PL_B_8']}", callback_data="get_top_playlists", style="primary"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('⚙')} {_['PL_B_4']}", callback_data="PM", style="primary"),
            rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
        )
    )


def top_play_markup(_):
    return (
        rich_button_row(
            rich_button(f"{pemoji('🔥')} {_['PL_B_9']}", callback_data="SERVERTOP Global", style="primary"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🔥')} {_['PL_B_10']}", callback_data="SERVERTOP Group", style="primary"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🔥')} {_['PL_B_11']}", callback_data="SERVERTOP Personal", style="primary"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="get_playmarkup", style="primary"),
            rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
        )
    )


def get_playlist_markup(_):
    return (
        rich_button_row(
            rich_button(f"{pemoji('🎧')} {_['P_B_1']}", callback_data="play_playlist a", style="primary"),
            rich_button(f"{pemoji('🎥')} {_['P_B_2']}", callback_data="play_playlist v", style="primary"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="home_play", style="primary"),
            rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
        )
    )


def failed_top_markup(_):
    return rich_button_row(
        rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="get_top_playlists", style="primary"),
        rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
    )


def warning_markup(_):
    return (
        rich_button_row(
            rich_button(f"{pemoji('🗑')} {_['PL_B_7']}", callback_data="delete_whole_playlist", style="danger"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="del_back_playlist", style="primary"),
            rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
        )
    )


def close_markup(_):
    return rich_button_row(
        rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
    )
