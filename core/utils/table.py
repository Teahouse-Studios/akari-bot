"""
Markdown 表格工具 - 单元格转义与「高度封顶、宽度按需」的列数求解。

平台的消息窗口容不下过长的消息，故表格一律以高度为准：行数封顶，条目变多时由列数吸收。
本模块只提供几何与转义，具体的单元格内容由调用方拼装 —— 模块侧要在单元格里嵌可点击标签，
适配器侧则是纯文本，两者的构造方式并不相同。
"""

import math
import re

# 表格的高度上限。条目增多时由列数吸收，使表格至多这么高。
TABLE_MAX_ROWS = 10

# 表格的最少列数。条目寥寥时若仍按高度上限反算列数会得到一两列的竖长条，
# 该下限只会让表更矮更宽，不会反过来撑高。
TABLE_MIN_COLUMNS = 3


def escape_table_cell(text: str) -> str:
    """
    把文本整理成可以放进 markdown 表格单元格的形态。

    :param text: 原始文本。
    :return: 可安全放入单元格的文本。
    """
    return text.replace("|", "\\|").replace("\r\n", "\n").replace("\n", "  <br>  ")


def format_table_code(text: str) -> str:
    """
    把文本包成 markdown 行内代码，使其中的格式标记不被解析。

    :param text: 原始文本。
    :return: 可安全放入单元格的行内代码；文本为空时返回空串。
    """
    if not text:
        return ""
    body = text.replace("|", "\\|").replace("\r\n", "\n").replace("\n", " ")
    longest = max((len(run) for run in re.findall(r"`+", body)), default=0)
    fence = "`" * (longest + 1)
    padding = " " if body.startswith("`") or body.endswith("`") else ""
    return f"{fence}{padding}{body}{padding}{fence}"


def resolve_table_columns(
    sizes: list[int],
    separators: int = 0,
    minimum: int = TABLE_MIN_COLUMNS,
    max_rows: int = TABLE_MAX_ROWS,
) -> int:
    """
    按高度上限反算表格的列数。

    自最少列数起逐步加宽，直到各节行数与区隔行之和落进高度上限；条目实在太多时以最大的
    一节为界收手，不再无谓加宽 —— 再宽也塞不下更多，只会白白拉长每一行。

    :param sizes: 各节的条目数量，均大于零。
    :param separators: 区隔行的数量，一并计入高度。
    :param minimum: 列数下限。
    :param max_rows: 高度上限。
    :return: 列数。
    """
    widest = max(sizes)
    columns = minimum
    while columns < widest:
        if sum(math.ceil(size / columns) for size in sizes) + separators <= max_rows:
            break
        columns += 1
    return min(columns, widest)
