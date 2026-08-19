
# All rights reserved.
#
from VenomX.utils.premium import (
    close_btn,
    music_btn,
    video_btn,
)


def song_markup(_, vidid):
    buttons = [
        [
            music_btn(
                _["SG_B_2"],
                f"song_helper audio|{vidid}",
            ),
            video_btn(
                _["SG_B_3"],
                f"song_helper video|{vidid}",
            ),
        ],
        [
            close_btn(_["CLOSE_BUTTON"]),
        ],
    ]
    return buttons
