"""Wiki 论坛列表 Markdown 表格布局测试。"""

from core.builtins.message.elements import ActionTextElement, MarkdownElement
from core.tester import Tester, func_case
from modules.wiki.utils.forum import (
    FORUM_TABLE_MAX_ROWS,
    build_forum_markdown_table,
    build_section_markdown_table,
)


def _forum_data(count: int) -> dict:
    return {
        "#": {"data": ["标题"]},
        **{str(index): {"text": f"主题 {index}", "data": [f"主题 {index}"]} for index in range(1, count + 1)},
    }


def _render_table_text(count: int) -> tuple[str, list[ActionTextElement]]:
    values = list(build_forum_markdown_table(_forum_data(count), "~"))
    actions = [value for value in values if isinstance(value, ActionTextElement)]
    markdown = "".join(value.text for value in values if isinstance(value, MarkdownElement))
    return markdown, actions


async def _test_forum_table_caps_height_and_expands_columns():
    markdown, actions = _render_table_text(FORUM_TABLE_MAX_ROWS * 2)
    return (
        len(actions) == 10
        and markdown.count("| --- | --- |") == 1
        and {action.show.text for action in actions} == {f"{index}. 主题 {index}" for index in range(1, 11)}
        and actions[1].text.text == "~wiki 主题 6"
    )


async def _test_forum_table_uses_one_column_for_five_topics():
    markdown, actions = _render_table_text(FORUM_TABLE_MAX_ROWS)
    return markdown.count("| --- |") == 1 and len(actions) == FORUM_TABLE_MAX_ROWS


async def _test_section_table_has_no_empty_top_row():
    values = list(build_section_markdown_table(["概要", "用法", "示例"], "讨论:页面", "~"))
    actions = [value for value in values if isinstance(value, ActionTextElement)]
    first_action = next(index for index, value in enumerate(values) if isinstance(value, ActionTextElement))
    return (
        first_action == 1
        and actions[0].show.text == "1. 概要"
        and actions[0].text.text == "~wiki 讨论:页面#概要"
        and actions[-1].show.text == "3. 示例"
    )


@func_case
async def test_wiki_forum(tester: Tester):
    await tester.test(_test_forum_table_caps_height_and_expands_columns, "论坛表格超过五条时向右扩展")
    await tester.test(_test_forum_table_uses_one_column_for_five_topics, "论坛表格五条以内保持单列")
    await tester.test(_test_section_table_has_no_empty_top_row, "讨论页章节表格不留空白顶行")
    return tester
