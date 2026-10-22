# All rights reserved.
#
# Rich-message settings markups (Bot API 10.3) — returns HTML fragments.
# Callback_data strings are kept identical to the old inline buttons.

from typing import Union

from VenomX.utils.rich_msg import (
    btn_off,
    btn_on,
    pemoji,
    rich_button,
    rich_button_row,
    rich_esc,
)


def _backclose(_):
    return rich_button_row(
        rich_button(
            f"{pemoji('🚀')} {_['BACK_BUTTON']}",
            callback_data="settingsback_helper",
            style="primary",
        ),
        rich_button(
            f"{pemoji('❌')} {_['CLOSE_BUTTON']}",
            callback_data="close",
            style="danger",
        ),
    )


def setting_markup(_):
    return (
        rich_button_row(
            rich_button(f"{pemoji('✅')} {_['ST_B_1']}", callback_data="AQ"),
            rich_button(f"{pemoji('🎥')} {_['ST_B_2']}", callback_data="VQ"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🎚')} {_['ST_B_3']}", callback_data="AU", style="primary"),
            rich_button(f"{pemoji('🌐')} {_['ST_B_6']}", callback_data="LG", style="primary"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🎮')} {_['ST_B_5']}", callback_data="PM", style="primary"),
            rich_button(f"{pemoji('🧹')} {_['ST_B_7']}", callback_data="CM", style="primary"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('⚡')} {_['ST_B_32']}", callback_data="IP", style="primary"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('❌')} {_['CLOSE_BUTTON']}", callback_data="close", style="danger"),
        )
    )


def audio_quality_markup(
    _,
    LOW: Union[bool, str] = None,
    MEDIUM: Union[bool, str] = None,
    HIGH: Union[bool, str] = None,
    STUDIO: Union[bool, str] = None,
):
    def aq(btn_text, cb, on):
        return rich_button(
            f"{pemoji('✅') if on else pemoji('🎧')} {rich_esc(btn_text)}",
            callback_data=cb,
            style="success" if on else "primary",
        )

    return (
        rich_button_row(
            aq(_["ST_B_8"], "LOW", LOW is True),
            aq(_["ST_B_9"], "MEDIUM", MEDIUM is True),
        )
        + rich_button_row(
            aq(_["ST_B_10"], "HIGH", HIGH is True),
            aq(_["ST_B_11"], "STUDIO", STUDIO is True),
        )
        + _backclose(_)
    )


def video_quality_markup(
    _,
    SD_360p: Union[bool, str] = None,
    SD_480p: Union[bool, str] = None,
    HD_720p: Union[bool, str] = None,
    FHD_1080p: Union[bool, str] = None,
    QHD_2K: Union[bool, str] = None,
    UHD_4K: Union[bool, str] = None,
):
    def vq(btn_text, cb, on):
        return rich_button(
            f"{pemoji('✅') if on else pemoji('🎥')} {rich_esc(btn_text)}",
            callback_data=cb,
            style="success" if on else "primary",
        )

    return (
        rich_button_row(
            vq(_["ST_B_12"], "SD_360p", SD_360p is True),
            vq(_["ST_B_13"], "SD_480p", SD_480p is True),
        )
        + rich_button_row(
            vq(_["ST_B_14"], "HD_720p", HD_720p is True),
            vq(_["ST_B_15"], "FHD_1080p", FHD_1080p is True),
        )
        + rich_button_row(
            vq(_["ST_B_16"], "QHD_2K", QHD_2K is True),
            vq(_["ST_B_17"], "UHD_4K", UHD_4K is True),
        )
        + _backclose(_)
    )


def cleanmode_settings_markup(
    _,
    status: Union[bool, str] = None,
    dels: Union[bool, str] = None,
):
    return (
        rich_button_row(
            rich_button(f"{pemoji('🧹')} {_['ST_B_7']}", callback_data="CMANSWER"),
            btn_on(_["ST_B_18"], "CLEANMODE")
            if status is True
            else btn_off(_["ST_B_19"], "CLEANMODE"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🧨')} {_['ST_B_30']}", callback_data="COMMANDANSWER"),
            btn_on(_["ST_B_18"], "COMMANDELMODE")
            if dels is True
            else btn_off(_["ST_B_19"], "COMMANDELMODE"),
        )
        + _backclose(_)
    )


def auth_users_markup(_, status: Union[bool, str] = None):
    return (
        rich_button_row(
            rich_button(f"{pemoji('🎚')} {_['ST_B_3']}", callback_data="AUTHANSWER"),
            btn_on(_["ST_B_20"], "AUTH")
            if status is True
            else btn_off(_["ST_B_21"], "AUTH"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🔗')} {_['ST_B_22']}", callback_data="AUTHLIST", style="primary"),
        )
        + _backclose(_)
    )


def playmode_users_markup(
    _,
    Direct: Union[bool, str] = None,
    Group: Union[bool, str] = None,
    Playtype: Union[bool, str] = None,
):
    return (
        rich_button_row(
            rich_button(f"{pemoji('🎮')} {_['ST_B_23']}", callback_data="SEARCHANSWER"),
            btn_on(_["ST_B_24"], "MODECHANGE")
            if Direct is True
            else btn_off(_["ST_B_25"], "MODECHANGE"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🎚')} {_['ST_B_26']}", callback_data="AUTHANSWER"),
            btn_on(_["ST_B_20"], "CHANNELMODECHANGE")
            if Group is True
            else btn_off(_["ST_B_21"], "CHANNELMODECHANGE"),
        )
        + rich_button_row(
            rich_button(f"{pemoji('🎧')} {_['ST_B_29']}", callback_data="PLAYTYPEANSWER"),
            btn_on(_["ST_B_20"], "PLAYTYPECHANGE")
            if Playtype is True
            else btn_off(_["ST_B_21"], "PLAYTYPECHANGE"),
        )
        + _backclose(_)
    )


def instantplay_markup(_, status: Union[bool, str] = None):
    return (
        rich_button_row(
            rich_button(f"{pemoji('⚡')} {_['ST_B_33']}", callback_data="INSTANTPLAYANSWER"),
            btn_on(_["ST_B_18"], "INSTANTPLAYCHANGE")
            if status is True
            else btn_off(_["ST_B_19"], "INSTANTPLAYCHANGE"),
        )
        + _backclose(_)
    )
