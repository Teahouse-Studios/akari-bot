"""按钮排布工具单元测试。"""

from core.logger import Logger
from core.tester import func_case, Tester
from core.utils.button import (
    DEFAULT_BUTTONS_PER_ROW,
    MAX_BUTTONS_PER_ROW,
    MAX_BUTTON_ROWS,
    arrange_buttons,
)


def _make_buttons(count: int) -> list[tuple[str, str]]:
    return [(f"label{i}", f"~cmd{i}") for i in range(count)]


def _row_sizes(count: int, per_row: int = DEFAULT_BUTTONS_PER_ROW) -> list[int]:
    return [len(row.buttons) for row in arrange_buttons(_make_buttons(count), per_row)]


def _test_empty_returns_no_rows() -> bool:
    if arrange_buttons([]) != []:
        Logger.error("Empty input should produce no rows")
        return False
    return True


def _test_row_sizes() -> bool:
    expected = {1: [1], 2: [2], 3: [3], 5: [3, 2], 7: [3, 2, 2], 12: [3, 3, 3, 3], 50: [10] * 5}
    for count, sizes in expected.items():
        actual = _row_sizes(count)
        if actual != sizes:
            Logger.error(f"{count} buttons should be arranged as {sizes}, got {actual}")
            return False
    return True


def _test_platform_limits_hold() -> bool:
    for count in range(1, 60):
        rows = arrange_buttons(_make_buttons(count))
        if len(rows) > MAX_BUTTON_ROWS:
            Logger.error(f"{count} buttons produced {len(rows)} rows, over the limit of {MAX_BUTTON_ROWS}")
            return False
        if any(len(row.buttons) > MAX_BUTTONS_PER_ROW for row in rows):
            Logger.error(f"{count} buttons produced a row over the limit of {MAX_BUTTONS_PER_ROW}")
            return False
    return True


def _test_order_and_content_preserved() -> bool:
    buttons = _make_buttons(12)
    flat = [(button.show, button.value) for row in arrange_buttons(buttons) for button in row.buttons]
    if flat != buttons:
        Logger.error("Arranging must preserve both the order and the content of the buttons")
        return False
    return True


def _test_overflow_is_truncated() -> bool:
    capacity = MAX_BUTTONS_PER_ROW * MAX_BUTTON_ROWS
    total = sum(len(row.buttons) for row in arrange_buttons(_make_buttons(capacity + 1)))
    if total != capacity:
        Logger.error(f"Overflowing input should be truncated to {capacity}, got {total}")
        return False
    return True


def _test_custom_per_row() -> bool:
    if _row_sizes(6, per_row=2) != [2, 2, 2]:
        Logger.error("A custom per_row should govern the row count")
        return False
    if _row_sizes(4, per_row=10) != [4]:
        Logger.error("A per_row above the button count should yield a single row")
        return False
    return True


def _test_duplicate_labels_are_preserved() -> bool:
    rows = arrange_buttons([("same", "~a"), ("same", "~b")])
    return [(button.show, button.value) for button in rows[0].buttons] == [("same", "~a"), ("same", "~b")]


@func_case
async def test_button_arrange(tester: Tester):
    """core.utils.button: 按钮排布工具测试"""
    await tester.test(_test_empty_returns_no_rows, "空输入无行测试")
    await tester.test(_test_row_sizes, "分行结果测试")
    await tester.test(_test_platform_limits_hold, "平台上限测试")
    await tester.test(_test_order_and_content_preserved, "顺序与内容守恒测试")
    await tester.test(_test_overflow_is_truncated, "超量截断测试")
    await tester.test(_test_custom_per_row, "自定义每行上限测试")
    await tester.test(_test_duplicate_labels_are_preserved, "重复展示文本保留测试")

    return tester
