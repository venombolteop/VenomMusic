
# All rights reserved.
#
# Rich-message song panel builder (replaces the InlineKeyboard rows list).

from VenomX.utils.rich_msg import pemoji, rich_button, rich_button_row


def song_markup(_, vidid):
    rows = rich_button_row(
        rich_button(
            f"{pemoji('🎵')} {_['SG_B_2']}",
            callback_data=f"song_helper audio|{vidid}",
            style="success",
        ),
        rich_button(
            f"{pemoji('🎥')} {_['SG_B_3']}",
            callback_data=f"song_helper video|{vidid}",
            style="primary",
        ),
    )
    rows += rich_button_row(
        rich_button(
            f"{pemoji('❌')} {_['CLOSE_BUTTON']}",
            callback_data="close",
            style="danger",
        )
    )
    return rows
