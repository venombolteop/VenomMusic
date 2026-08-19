# All rights reserved.
#
from typing import Union

from VenomX.utils.premium import (
    back_btn,
    close_btn,
    custom_btn,
    music_btn,
    on_btn,
    off_btn,
    settings_btn,
)
from pyrogram.enums import ButtonStyle


def setting_markup(_):
    buttons = [
        [
            settings_btn(_["ST_B_1"], "AQ"),
            settings_btn(_["ST_B_2"], "VQ"),
        ],
        [
            settings_btn(_["ST_B_3"], "AU"),
            settings_btn(_["ST_B_6"], "LG"),
        ],
        [
            settings_btn(_["ST_B_5"], "PM"),
            settings_btn(_["ST_B_7"], "CM"),
        ],
        [
            settings_btn(_["ST_B_32"], "IP"),
        ],
        [
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def audio_quality_markup(
    _,
    LOW: Union[bool, str] = None,
    MEDIUM: Union[bool, str] = None,
    HIGH: Union[bool, str] = None,
    STUDIO: Union[bool, str] = None,
):
    buttons = [
        [
            custom_btn(
                text=_["ST_B_8"].format("✅") if LOW == True else _["ST_B_8"].format(""),
                callback_data="LOW",
                style=ButtonStyle.SUCCESS if LOW == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
            custom_btn(
                text=_["ST_B_9"].format("✅") if MEDIUM == True else _["ST_B_9"].format(""),
                callback_data="MEDIUM",
                style=ButtonStyle.SUCCESS if MEDIUM == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
        ],
        [
            custom_btn(
                text=_["ST_B_10"].format("✅") if HIGH == True else _["ST_B_10"].format(""),
                callback_data="HIGH",
                style=ButtonStyle.SUCCESS if HIGH == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
            custom_btn(
                text=_["ST_B_11"].format("✅") if STUDIO == True else _["ST_B_11"].format(""),
                callback_data="STUDIO",
                style=ButtonStyle.SUCCESS if STUDIO == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
        ],
        [
            back_btn(_["BACK_BUTTON"], "settingsback_helper"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def video_quality_markup(
    _,
    SD_360p: Union[bool, str] = None,
    SD_480p: Union[bool, str] = None,
    HD_720p: Union[bool, str] = None,
    FHD_1080p: Union[bool, str] = None,
    QHD_2K: Union[bool, str] = None,
    UHD_4K: Union[bool, str] = None,
):
    buttons = [
        [
            custom_btn(
                text=_["ST_B_12"].format("✅") if SD_360p == True else _["ST_B_12"].format(""),
                callback_data="SD_360p",
                style=ButtonStyle.SUCCESS if SD_360p == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
            custom_btn(
                text=_["ST_B_13"].format("✅") if SD_480p == True else _["ST_B_13"].format(""),
                callback_data="SD_480p",
                style=ButtonStyle.SUCCESS if SD_480p == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
        ],
        [
            custom_btn(
                text=_["ST_B_14"].format("✅") if HD_720p == True else _["ST_B_14"].format(""),
                callback_data="HD_720p",
                style=ButtonStyle.SUCCESS if HD_720p == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
            custom_btn(
                text=_["ST_B_15"].format("✅") if FHD_1080p == True else _["ST_B_15"].format(""),
                callback_data="FHD_1080p",
                style=ButtonStyle.SUCCESS if FHD_1080p == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
        ],
        [
            custom_btn(
                text=_["ST_B_16"].format("✅") if QHD_2K == True else _["ST_B_16"].format(""),
                callback_data="QHD_2K",
                style=ButtonStyle.SUCCESS if QHD_2K == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
            custom_btn(
                text=_["ST_B_17"].format("✅") if UHD_4K == True else _["ST_B_17"].format(""),
                callback_data="UHD_4K",
                style=ButtonStyle.SUCCESS if UHD_4K == True else ButtonStyle.PRIMARY,
                emoji="✅",
            ),
        ],
        [
            back_btn(_["BACK_BUTTON"], "settingsback_helper"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def cleanmode_settings_markup(
    _,
    status: Union[bool, str] = None,
    dels: Union[bool, str] = None,
):
    buttons = [
        [
            settings_btn(_["ST_B_7"], "CMANSWER"),
            on_btn(_["ST_B_18"], "CLEANMODE") if status == True else off_btn(_["ST_B_19"], "CLEANMODE"),
        ],
        [
            settings_btn(_["ST_B_30"], "COMMANDANSWER"),
            on_btn(_["ST_B_18"], "COMMANDELMODE") if dels == True else off_btn(_["ST_B_19"], "COMMANDELMODE"),
        ],
        [
            back_btn(_["BACK_BUTTON"], "settingsback_helper"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def auth_users_markup(_, status: Union[bool, str] = None):
    buttons = [
        [
            settings_btn(_["ST_B_3"], "AUTHANSWER"),
            on_btn(_["ST_B_20"], "AUTH") if status == True else off_btn(_["ST_B_21"], "AUTH"),
        ],
        [
            settings_btn(_["ST_B_22"], "AUTHLIST"),
        ],
        [
            back_btn(_["BACK_BUTTON"], "settingsback_helper"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def playmode_users_markup(
    _,
    Direct: Union[bool, str] = None,
    Group: Union[bool, str] = None,
    Playtype: Union[bool, str] = None,
):
    buttons = [
        [
            settings_btn(_["ST_B_23"], "SEARCHANSWER"),
            on_btn(_["ST_B_24"], "MODECHANGE") if Direct == True else off_btn(_["ST_B_25"], "MODECHANGE"),
        ],
        [
            settings_btn(_["ST_B_26"], "AUTHANSWER"),
            on_btn(_["ST_B_20"], "CHANNELMODECHANGE") if Group == True else off_btn(_["ST_B_21"], "CHANNELMODECHANGE"),
        ],
        [
            settings_btn(_["ST_B_29"], "PLAYTYPEANSWER"),
            on_btn(_["ST_B_20"], "PLAYTYPECHANGE") if Playtype == True else off_btn(_["ST_B_21"], "PLAYTYPECHANGE"),
        ],
        [
            back_btn(_["BACK_BUTTON"], "settingsback_helper"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons


def instantplay_markup(_, status: Union[bool, str] = None):
    buttons = [
        [
            settings_btn(_["ST_B_33"], "INSTANTPLAYANSWER"),
            on_btn(_["ST_B_18"], "INSTANTPLAYCHANGE") if status == True else off_btn(_["ST_B_19"], "INSTANTPLAYCHANGE"),
        ],
        [
            back_btn(_["BACK_BUTTON"], "settingsback_helper"),
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons
