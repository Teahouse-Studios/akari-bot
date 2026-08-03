"""按钮排布工具单元测试。

平台允许单行 10 个按钮、最多 5 行，但一行塞满 10 个会挤到显示不全，故默认按可读性上限
分行，仅在总数超出「上限 × 5 行」时才放宽至硬上限。行数定下后均分，是为避免末行只剩
一两个按钮的参差排版。
"""

from unittest.mock import patch

from core.logger import Logger
from core.tester import func_case, Tester
from core.utils.button import (
    DEFAULT_BUTTONS_PER_ROW,
    MAX_BUTTONS_PER_ROW,
    MAX_BUTTON_ROWS,
    arrange_buttons,
)


def _make_buttons(count: int) -> list[tuple[str, str]]:
    """构造若干标签互异的按钮。

    :param count: 按钮数量。
    :return: （标签, 命令）序列。
    """
    return [(f"label{i}", f"~cmd{i}") for i in range(count)]


def _row_sizes(count: int, per_row: int = DEFAULT_BUTTONS_PER_ROW) -> list[int]:
    """取排布结果中各行的按钮数量。

    :param count: 按钮数量。
    :param per_row: 每行按钮数量的可读性上限。
    :return: 各行的按钮数量。
    """
    return [len(row) for row in arrange_buttons(_make_buttons(count), per_row)]


def _test_empty_returns_no_rows() -> bool:
    """无按钮时不应产出空行，否则平台会收到一个空键盘"""
    if arrange_buttons([]) != []:
        Logger.error("Empty input should produce no rows")
        return False
    return True


def _test_row_sizes() -> bool:
    """默认上限下的分行结果"""
    expected = {1: [1], 2: [2], 3: [3], 5: [3, 2], 7: [3, 2, 2], 12: [3, 3, 3, 3], 50: [10] * 5}
    for count, sizes in expected.items():
        actual = _row_sizes(count)
        if actual != sizes:
            Logger.error(f"{count} buttons should be arranged as {sizes}, got {actual}")
            return False
    return True


def _test_platform_limits_hold() -> bool:
    """任何输入下都不得突破平台的每行数量与行数上限"""
    for count in range(1, 60):
        rows = arrange_buttons(_make_buttons(count))
        if len(rows) > MAX_BUTTON_ROWS:
            Logger.error(f"{count} buttons produced {len(rows)} rows, over the limit of {MAX_BUTTON_ROWS}")
            return False
        if any(len(row) > MAX_BUTTONS_PER_ROW for row in rows):
            Logger.error(f"{count} buttons produced a row over the limit of {MAX_BUTTONS_PER_ROW}")
            return False
    return True


def _test_order_and_content_preserved() -> bool:
    """排布不得打乱顺序或丢失按钮"""
    buttons = _make_buttons(12)
    flat = [(label, command) for row in arrange_buttons(buttons) for label, command in row.items()]
    if flat != buttons:
        Logger.error("Arranging must preserve both the order and the content of the buttons")
        return False
    return True


def _test_overflow_is_truncated() -> bool:
    """超出容量时截断至容量上限，而非硬塞进最后一行"""
    capacity = MAX_BUTTONS_PER_ROW * MAX_BUTTON_ROWS
    total = sum(len(row) for row in arrange_buttons(_make_buttons(capacity + 1)))
    if total != capacity:
        Logger.error(f"Overflowing input should be truncated to {capacity}, got {total}")
        return False
    return True


def _test_custom_per_row() -> bool:
    """可读性上限可由调用方指定"""
    if _row_sizes(6, per_row=2) != [2, 2, 2]:
        Logger.error("A custom per_row should govern the row count")
        return False
    if _row_sizes(4, per_row=10) != [4]:
        Logger.error("A per_row above the button count should yield a single row")
        return False
    return True


def _test_duplicate_labels_warn() -> bool:
    """同一行内的重复标签会在转为字典时互相覆盖，须给出告警"""
    warned = []
    with patch.object(Logger, "warning", lambda message: warned.append(message)):
        rows = arrange_buttons([("same", "~a"), ("same", "~b")])
    if not warned:
        Logger.error("Duplicate labels within one row should emit a warning")
        return False
    if rows != [{"same": "~b"}]:
        Logger.error(f"Duplicate labels collapse to the last one, got {rows}")
        return False
    return True


@func_case
async def test_button_arrange(tester: Tester):
    """core.utils.button: 按钮排布工具测试"""
    await tester.test(_test_empty_returns_no_rows, "空输入无行测试")
    await tester.test(_test_row_sizes, "分行结果测试")
    await tester.test(_test_platform_limits_hold, "平台上限测试")
    await tester.test(_test_order_and_content_preserved, "顺序与内容守恒测试")
    await tester.test(_test_overflow_is_truncated, "超量截断测试")
    await tester.test(_test_custom_per_row, "自定义每行上限测试")
    await tester.test(_test_duplicate_labels_warn, "重复标签告警测试")

    return tester
