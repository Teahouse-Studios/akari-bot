"""论坛页面列表的消息渲染工具。"""

import math

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, Markdown
from core.utils.table import escape_table_cell

FORUM_TABLE_MAX_ROWS = 5


def build_forum_markdown_table(forum_data: dict, command_prefix: str) -> MessageChain:
    """将论坛帖子列表渲染为可点击的 Markdown 表格。

    每个单元格都是一个 ActionText，点击后把对应的 Wiki 查询命令填入输入框。
    表格最多使用五行，超过五条帖子后从右侧追加列，并保持帖子编号按列递增。
    """
    topics = []
    for key, value in forum_data.items():
        if key == "#" or not isinstance(value, dict):
            continue
        data = value.get("data") or []
        display_title = data[0] if data else value.get("text")
        command_title = value.get("text") or display_title
        if display_title and command_title:
            topics.append((str(len(topics) + 1), str(display_title), str(command_title)))
    if not topics:
        return MessageChain.create()

    columns = max(1, math.ceil(len(topics) / FORUM_TABLE_MAX_ROWS))
    rows = min(len(topics), FORUM_TABLE_MAX_ROWS)
    separator = "| " + " | ".join("---" for _ in range(columns)) + " |\n"
    pending = "| " + " | ".join("" for _ in range(columns)) + " |\n" + separator
    parts = []

    for row in range(rows):
        pending += "| "
        for column in range(columns):
            index = row + column * FORUM_TABLE_MAX_ROWS
            if index >= len(topics):
                pending += " | "
                continue
            number, display_title, command_title = topics[index]
            display = escape_table_cell(f"{number}. {display_title}")
            parts.append(Markdown(pending, disable_joke=True))
            parts.append(ActionText(f"{command_prefix}wiki {command_title}", show=display))
            pending = " | "
        pending = pending.rstrip() + "\n"

    parts.append(Markdown(pending, disable_joke=True))
    return MessageChain.assign(parts)


__all__ = ["FORUM_TABLE_MAX_ROWS", "build_forum_markdown_table"]
