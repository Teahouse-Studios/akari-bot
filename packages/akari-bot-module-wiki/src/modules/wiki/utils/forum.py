"""Wiki 讨论页列表的消息渲染工具。"""

import math

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, Markdown
from core.utils.table import escape_table_cell

FORUM_TABLE_MAX_ROWS = 5


def build_markdown_choice_table(choices: list[tuple[str, str]], command_prefix: str) -> MessageChain:
    """将 Wiki 选择项渲染为可点击的 Markdown 表格。"""
    if not choices:
        return MessageChain.create()

    columns = max(1, math.ceil(len(choices) / FORUM_TABLE_MAX_ROWS))
    rows = min(len(choices), FORUM_TABLE_MAX_ROWS)
    separator = "| " + " | ".join("---" for _ in range(columns)) + " |\n"
    pending = ""
    parts = []

    for row in range(rows):
        pending += "| "
        for column in range(columns):
            index = row + column * FORUM_TABLE_MAX_ROWS
            if index >= len(choices):
                pending += " | "
                continue
            display_title, command_title = choices[index]
            parts.append(Markdown(pending, disable_joke=True))
            parts.append(
                ActionText(
                    f"{command_prefix}wiki {command_title}",
                    show=escape_table_cell(f"{index + 1}. {display_title}"),
                )
            )
            pending = " | "
        pending = pending.rstrip() + "\n"
        if row == 0:
            pending += separator

    parts.append(Markdown(pending, disable_joke=True))
    return MessageChain.assign(parts)


def build_forum_markdown_table(forum_data: dict, command_prefix: str) -> MessageChain:
    """将论坛帖子列表渲染为可点击的 Markdown 表格。"""
    choices = []
    for key, value in forum_data.items():
        if key == "#" or not isinstance(value, dict):
            continue
        data = value.get("data") or []
        display_title = data[0] if data else value.get("text")
        command_title = value.get("text") or display_title
        if display_title and command_title:
            choices.append((str(display_title), str(command_title)))
    return build_markdown_choice_table(choices, command_prefix)


def build_section_markdown_table(sections: list[str], page_title: str, command_prefix: str) -> MessageChain:
    """将讨论页章节列表渲染为可点击的 Markdown 表格。"""
    return build_markdown_choice_table([(section, f"{page_title}#{section}") for section in sections], command_prefix)


__all__ = [
    "FORUM_TABLE_MAX_ROWS",
    "build_forum_markdown_table",
    "build_markdown_choice_table",
    "build_section_markdown_table",
]
