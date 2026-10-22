
# All rights reserved.
#
# Rich-message keyboard helpers — return rich HTML ("<tg-button-row>" rows)
# instead of pyrogram InlineKeyboardMarkup. Pair with VenomX.utils.rich_msg.

from .functions import get_urls_from_text as is_url
from .rich_msg import rich_button_row


_STYLES = ["primary", "success", "danger", "primary"]


def keyboard(buttons_list, row_width: int = 2):
    rows = []
    row = []
    idx = 0
    for item in buttons_list:
        text, action = str(item[0]), str(item[1])
        style = _STYLES[idx % len(_STYLES)]
        idx += 1
        if is_url(action):
            row.append(
                f'<tg-button type="url" style="{style}" '
                f'url="{action}">{text}</tg-button>'
            )
        else:
            row.append(
                f'<tg-button type="callback_data" style="{style}" '
                f'data="{action}">{text}</tg-button>'
            )
        if len(row) == row_width:
            rows.append(rich_button_row(*row))
            row = []
    if row:
        rows.append(rich_button_row(*row))
    return "".join(rows)


def ikb(data: dict, row_width: int = 2):
    return keyboard(data.items(), row_width=row_width)
