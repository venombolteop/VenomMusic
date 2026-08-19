
# All rights reserved.

from pykeyboard import InlineKeyboard

from .functions import get_urls_from_text as is_url
from .premium import custom_btn


def keyboard(buttons_list, row_width: int = 2):
    buttons = InlineKeyboard(row_width=row_width)
    data = [
        (
            custom_btn(text=str(i[0]), callback_data=str(i[1]))
            if not is_url(i[1])
            else custom_btn(text=str(i[0]), url=str(i[1]))
        )
        for i in buttons_list
    ]
    buttons.add(*data)
    return buttons


def ikb(data: dict, row_width: int = 2):
    return keyboard(data.items(), row_width=row_width)
