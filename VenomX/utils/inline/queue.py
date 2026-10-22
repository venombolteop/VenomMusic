
#
# All rights reserved.
#
# Rich-message versions of the queue panels (Bot API 10.3 sendRichMessage).
# These return rich HTML fragments; combine with the panel text and send via
# VenomX.utils.rich_msg.send_rich / edit_rich.

from VenomX.utils.rich_msg import pemoji, rich_button, rich_button_row


def queue_markup(
    _,
    DURATION,
    CPLAY,
    videoid,
    played: bool | int = None,
    dur: bool | int = None,
):
    rows = ""
    if DURATION != "Unknown":
        rows += rich_button_row(
            rich_button(
                f"{pemoji('⏱')} {_['QU_B_2'].format(played, dur)}",
                callback_data="GetTimer",
                style="primary",
            )
        )
    rows += rich_button_row(
        rich_button(
            f"{pemoji('🎵')} {_['QU_B_1']}",
            callback_data=f"GetQueued {CPLAY}|{videoid}",
            style="primary",
        ),
        rich_button(
            f"{pemoji('❌')} {_['CLOSEMENU_BUTTON']}",
            callback_data="close",
            style="danger",
        ),
    )
    return rows


def queue_back_markup(_, CPLAY):
    return rich_button_row(
        rich_button(
            f"{pemoji('🚀')} {_['BACK_BUTTON']}",
            callback_data=f"queue_back_timer {CPLAY}",
            style="primary",
        ),
        rich_button(
            f"{pemoji('❌')} {_['CLOSE_BUTTON']}",
            callback_data="close",
            style="danger",
        ),
    )
