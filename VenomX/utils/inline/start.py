
# All rights reserved.
#
# Rich-message start/help (Bot API 10.3) — HTML fragments.
#

from typing import Union

from config import GITHUB_REPO, SUPPORT_CHANNEL, SUPPORT_GROUP
from VenomX import app
from VenomX.utils.rich_msg import (
    pemoji,
    rich_button,
    rich_button_row,
    rich_url_button,
)


def _support_rows(_):
    rows = []
    if SUPPORT_CHANNEL and SUPPORT_GROUP:
        rows.append(
            rich_button_row(
                rich_url_button(f"{pemoji('📢')} {_['S_B_4']}", f"{SUPPORT_CHANNEL}"),
                rich_url_button(f"{pemoji('💬')} {_['S_B_3']}", f"{SUPPORT_GROUP}"),
            )
        )
    else:
        if SUPPORT_CHANNEL:
            rows.append(rich_button_row(rich_url_button(f"{pemoji('📢')} {_['S_B_4']}", f"{SUPPORT_CHANNEL}")))
        if SUPPORT_GROUP:
            rows.append(rich_button_row(rich_url_button(f"{pemoji('💬')} {_['S_B_3']}", f"{SUPPORT_GROUP}")))
    return "".join(rows)


def start_pannel(_):
    rows = rich_button_row(
        rich_url_button(f"{pemoji('⭐')} {_['S_B_1']}", f"https://t.me/{app.username}?start=help"),
        rich_button(f"{pemoji('⚙')} {_['S_B_2']}", callback_data="settings_helper"),
    )
    return rows + _support_rows(_)


def private_panel(_, BOT_USERNAME, OWNER: Union[bool, int] = None):
    rows = rich_button_row(
        rich_button(f"{pemoji('🚀')} {_['S_B_8']}", callback_data="settings_back_helper"),
    )
    rows += _support_rows(_)
    rows += rich_button_row(
        rich_url_button(f"{pemoji('🧲')} {_['S_B_5']}", f"https://t.me/{BOT_USERNAME}?startgroup=true"),
    )
    if GITHUB_REPO and OWNER:
        rows += rich_button_row(
            rich_url_button(f"{pemoji('👑')} {_['S_B_7']}", f"tg://user?id={OWNER}"),
            rich_url_button(f"{pemoji('🖥')} {_['S_B_6']}", f"{GITHUB_REPO}"),
        )
    else:
        if GITHUB_REPO:
            rows += rich_button_row(
                rich_url_button(f"{pemoji('🖥')} {_['S_B_6']}", f"{GITHUB_REPO}"),
            )
        if OWNER:
            rows += rich_button_row(
                rich_url_button(f"{pemoji('👑')} {_['S_B_7']}", f"tg://user?id={OWNER}"),
            )
    rows += rich_button_row(
        rich_button(f"{pemoji('🌐')} {_['ST_B_6']}", callback_data="LG"),
    )
    return rows


def support_group_markup(_):
    return rich_button_row(
        rich_url_button(f"{pemoji('💬')} {_['S_B_3']}", SUPPORT_GROUP),
    )


def help_back_markup(_):
    return rich_button_row(
        rich_button(f"{pemoji('🚀')} {_['BACK_BUTTON']}", callback_data="settings_back_helper"),
        rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
    )


def private_help_panel(_):
    return rich_button_row(
        rich_url_button(f"{pemoji('⭐')} {_['S_B_1']}", f"https://t.me/{app.username}?start=help"),
    )
