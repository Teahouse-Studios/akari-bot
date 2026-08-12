"""
按钮排布工具 - 将扁平的按钮序列整理为消息底部键盘所需的按行结构。

平台允许单行至多 10 个按钮、至多 5 行，但一行真塞满 10 个会挤到显示不全，
故另设一个可读性上限作为默认值，仅在按钮总数超出「可读性上限 × 5 行」时才放宽至硬上限。
"""

import math

from core.builtins.message.elements import ButtonElement, ButtonRows
from core.logger import Logger

# 平台单行按钮数量的硬上限
MAX_BUTTONS_PER_ROW = 10

# 平台按钮行数的硬上限
MAX_BUTTON_ROWS = 5

# 可读性上限，即默认的每行按钮数量
DEFAULT_BUTTONS_PER_ROW = 3

# MessageChain 自动排布单个 Button 时，每行的按钮数量
AUTO_BUTTONS_PER_ROW = 10

# MessageChain 自动排布单个 Button 时，允许生成的最大行数
AUTO_BUTTON_MAX_ROWS = 5


def arrange_buttons(
    buttons: list[tuple[str, str]],
    per_row: int = DEFAULT_BUTTONS_PER_ROW,
) -> list[ButtonRows]:
    """
    将（展示文本, 点击数据）序列整理为 ``ButtonFrame`` 所需的按钮行。

    行数由 ``per_row`` 算出后即固定，再把按钮均分到各行，使各行的数量至多相差一个——
    直接按 ``per_row`` 切片会得到 ``[3, 3, 3, 1]`` 这样参差的末行。行数超出平台上限时
    压回上限，此时每行的数量将突破 ``per_row``，至多到 ``MAX_BUTTONS_PER_ROW``。

    :param buttons: （标签, 命令）序列。标签为按钮上展示的文本，命令为点击后发出的内容。
    :param per_row: 每行按钮数量的可读性上限。
    :return: 按钮行列表；输入为空时返回空列表。
    """
    if not buttons:
        return []

    capacity = MAX_BUTTONS_PER_ROW * MAX_BUTTON_ROWS
    if len(buttons) > capacity:
        Logger.warning(
            f"Got {len(buttons)} buttons but only {capacity} fit; dropped the last {len(buttons) - capacity}."
        )
        buttons = buttons[:capacity]

    per_row = max(1, min(per_row, MAX_BUTTONS_PER_ROW))
    rows_count = min(math.ceil(len(buttons) / per_row), MAX_BUTTON_ROWS)
    base, extra = divmod(len(buttons), rows_count)

    rows = []
    start = 0
    for index in range(rows_count):
        # 余数均摊到靠前的几行，使各行数量至多相差一个
        size = base + 1 if index < extra else base
        row = buttons[start : start + size]
        start += size
        rows.append(ButtonRows.assign([ButtonElement.assign(show, value) for show, value in row]))
    return rows


def build_button_rows(rows: list[dict[str, str]]) -> list[ButtonRows]:
    """把旧式的按行映射转换为类型化按钮行。"""
    return [ButtonRows.assign([ButtonElement.assign(show, value) for show, value in row.items()]) for row in rows]
