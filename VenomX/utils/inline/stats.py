
# All rights reserved.
#
# Rich-message stats markups (Bot API 10.3) — HTML fragments.
#

from VenomX import app
from VenomX.utils.rich_msg import (
    pemoji,
    rich_button,
    rich_button_row,
    rich_url_button,
)


def back_stats_markup(_):
    return rich_button_row(
        rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="TOPMARKUPGET"),
        rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
    )


def overallback_stats_markup(_):
    return rich_button_row(
        rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="GlobalStats"),
        rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
    )


def get_stats_markup(_, status):
    not_sudo_row = rich_button_row(
        rich_button(f"{pemoji('❌')} {_['CLOSEMENU_BUTTON']}", callback_data="close", style="danger"),
    )
    sudo_row = rich_button_row(
        rich_button(f"{pemoji('🔥')} {_['SA_B_8']}", callback_data="bot_stats_sudo g"),
        rich_button(f"{pemoji('❌')} {_['CLOSEMENU_BUTTON']}", callback_data="close", style="danger"),
    )
    return (
        rich_button_row(
            rich_button(f"{pemoji('🔥')} {_['SA_B_7']}", callback_data="TOPMARKUPGET"),
        )
        + rich_button_row(
            rich_url_button(f"{pemoji('🔗')} {_['SA_B_6']}", f"https://t.me/{app.username}?start=stats"),
            rich_button(f"{pemoji('🔥')} {_['SA_B_5']}", callback_data="TopOverall g"),
        )
        + (sudo_row if status else not_sudo_row)
    )


def stats_buttons(_, status):
    not_sudo = rich_button_row(
        rich_button(f"{pemoji('🔥')} {_['SA_B_5']}", callback_data="TopOverall s"),
    )
    sudo = rich_button_row(
        rich_button(f"{pemoji('🔥')} {_['SA_B_8']}", callback_data="bot_stats_sudo s"),
        rich_button(f"{pemoji('🔥')} {_['SA_B_5']}", callback_data="TopOverall s"),
    )
    return (sudo if status else not_sudo) + rich_button_row(
        rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
    )


def back_stats_buttons(_):
    return rich_button_row(
        rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="GETSTATS"),
        rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
    )


def top_ten_stats_markup(_):
    return (
        rich_button_row(
            rich_button(f"{pemoji('🔥')} {_['SA_B_2']}", callback_data="GetStatsNow Tracks"),
            rich_button(f"{pemoji('🔥')} {_['SA_B_1']}", callback_data="GetStatsNow Chats"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🔥')} {_['SA_B_3']}", callback_data="GetStatsNow Users"),
            rich_button(f"{pemoji('🔥')} {_['SA_B_4']}", callback_data="GetStatsNow Here"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="GlobalStats"),
            rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
        )
    )
