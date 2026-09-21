"""消息节点在 QQBot 上的表格化测试。"""

from unittest.mock import patch

from botpy.message import GroupMessage

import bots.qqbot.context as qqbot_context
from bots.qqbot.context import MESSAGE_NODES_MAX_ROWS, QQBotContextManager, nodes_to_table
from bots.qqbot.features import guild_features
from bots.qqbot.info import target_group_prefix
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import Markdown, Plain
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.tester import func_case, Tester

BACKSLASH = chr(92)


def _make_session() -> SessionInfo:
    return SessionInfo(
        target_id=f"{target_group_prefix}|fake_group",
        sender_id="QQBot|1",
        target_from=target_group_prefix,
        client_name="QQBot",
        session_id="nodes-table",
        support_markdown=True,
    )


def _make_nodes(count: int, text: str = "内容") -> MessageNodes:
    return MessageNodes.assign([MessageChain.assign(Plain(f"{text}{i}")) for i in range(count)], name="标题")


def _unescaped_pipes(line: str) -> int:
    count, prev = 0, ""
    for char in line:
        if char == "|" and prev != BACKSLASH:
            count += 1
        prev = char
    return count


def _test_nodes_disabled_without_table_support() -> bool:
    if guild_features.support_markdown_extension or guild_features.support_handle_message_nodes:
        Logger.error("QQBot guild sessions without markdown tables should not handle message nodes as tables")
        return False
    return True


def _test_table_shape() -> bool:
    session_info = _make_session()
    for count in (1, 3, 10, 99):
        lines = nodes_to_table(session_info, _make_nodes(count)).split("\n")
        # 首行为表头、次行为分隔行，其余成对出现
        pairs = (len(lines) - 2) // 2
        if pairs > MESSAGE_NODES_MAX_ROWS:
            Logger.error(f"{count} nodes produced {pairs} row pairs, over the limit of {MESSAGE_NODES_MAX_ROWS}")
            return False
        columns = -(-count // MESSAGE_NODES_MAX_ROWS)
        if lines[1] != "|" + "---|" * columns:
            Logger.error(f"{count} nodes should render {columns} columns, got {lines[1]!r}")
            return False
    return True


def _test_rows_are_uniform() -> bool:
    session_info = _make_session()
    for count in range(1, 40):
        lines = nodes_to_table(session_info, _make_nodes(count)).split("\n")
        widths = {_unescaped_pipes(line) for line in lines}
        if len(widths) != 1:
            Logger.error(f"{count} nodes produced ragged rows: {lines}")
            return False
    return True


def _test_index_sits_above_content() -> bool:
    lines = nodes_to_table(_make_session(), _make_nodes(5)).split("\n")
    data = lines[2:]
    seen = 0
    for start in range(0, len(data), 2):
        numbers = [cell.strip() for cell in data[start].strip("|").split("|")]
        contents = [cell.strip() for cell in data[start + 1].strip("|").split("|")]
        for number, content in zip(numbers, contents):
            if not number:
                # 末对的空单元格，其下方亦须为空
                if content:
                    Logger.error(f"A padded index cell should sit above an empty content cell, got {content!r}")
                    return False
                continue
            seen += 1
            if number != str(seen) or content != f"内容{seen - 1}":
                Logger.error(f"Expected {seen} above 内容{seen - 1}, got {number!r} above {content!r}")
                return False
    if seen != 5:
        Logger.error(f"All five nodes should appear, got {seen}")
        return False
    return True


def _test_name_is_the_header() -> bool:
    lines = nodes_to_table(_make_session(), _make_nodes(2)).split("\n")
    if not lines[0].startswith("| 标题 |"):
        Logger.error(f"The node group name should head the table, got {lines[0]!r}")
        return False
    return True


def _test_multiline_content_uses_br() -> bool:
    nodes = MessageNodes.assign([MessageChain.assign(Plain("第一行\n第二行"))], name="标题")
    table = nodes_to_table(_make_session(), nodes)
    if "第一行  <br>  第二行" not in table:
        Logger.error(f"Newlines inside a cell should become <br>, got {table!r}")
        return False
    # 表头、分隔行、编号行、内容行共四行
    if len(table.split("\n")) != 4:
        Logger.error(f"A single multi-line node should still render one index/content pair, got {table!r}")
        return False
    return True


def _test_pipes_are_escaped() -> bool:
    nodes = MessageNodes.assign([MessageChain.assign(Plain("甲|乙"))], name="标题")
    table = nodes_to_table(_make_session(), nodes)
    if f"甲{BACKSLASH}|乙" not in table:
        Logger.error(f"Pipes inside a cell should be escaped, got {table!r}")
        return False
    return True


class _FakeGroupMessage(GroupMessage):
    def __init__(self):
        self.id = "source-message"
        self.group_openid = "fake_group"
        self.message_scene = None


class _FakeClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def send(self, target, **kwargs):
        self.calls.append(kwargs)
        return {"id": "sent-1"}

    async def send_markdown(self, target, content, keyboard=None):
        self.calls.append({"markdown": {"content": content}, "keyboard": keyboard})
        return {"id": "sent-1"}


async def _test_nodes_use_markdown_element() -> bool:
    session_id = "nodes-send"
    session_info = _make_session()
    session_info.session_id = session_id
    ctx = _FakeGroupMessage()
    client = _FakeClient()
    QQBotContextManager.context[session_id] = ctx
    try:
        with (
            patch.object(qqbot_context, "qq_use_markdown", True),
            patch.object(QQBotContextManager, "client", client),
        ):
            await QQBotContextManager.send_message(session_info, _make_nodes(3), quote=False)
    finally:
        QQBotContextManager.context.pop(session_id, None)

    if not client.calls:
        Logger.error("Sending message nodes should reach the platform")
        return False
    sent = client.calls[0]
    if "markdown" not in sent:
        Logger.error(f"A node table must be sent as markdown, got {sorted(sent)}")
        return False
    return True


async def _test_markdown_element_selects_markdown_path() -> bool:
    table = "| 正则 |  |\n|---|---|\n| a | b |"
    for element, expect_markdown in ((Markdown(table), True), (Plain(table), False)):
        session_id = f"markdown-element-{expect_markdown}"
        session_info = _make_session()
        session_info.session_id = session_id
        ctx = _FakeGroupMessage()
        client = _FakeClient()
        QQBotContextManager.context[session_id] = ctx
        try:
            with (
                patch.object(qqbot_context, "qq_use_markdown", True),
                patch.object(QQBotContextManager, "client", client),
            ):
                await QQBotContextManager.send_message(session_info, MessageChain.assign(element), quote=False)
        finally:
            QQBotContextManager.context.pop(session_id, None)
        if not client.calls:
            Logger.error(f"Sending should reach the platform (markdown={expect_markdown})")
            return False
        sent_markdown = "markdown" in client.calls[0]
        if sent_markdown is not expect_markdown:
            Logger.error(
                f"Markdown element={expect_markdown} should send as markdown={expect_markdown}, "
                f"got {sorted(client.calls[0])}"
            )
            return False
    return True


@func_case
async def test_qqbot_message_nodes(tester: Tester):
    """bots.qqbot.context: 消息节点表格化测试"""
    await tester.test(_test_nodes_disabled_without_table_support, "无表格能力时节点使用图片回退测试")
    await tester.test(_test_table_shape, "表格行列数测试")
    await tester.test(_test_rows_are_uniform, "表格列数齐平测试")
    await tester.test(_test_index_sits_above_content, "编号在上内容在下测试")
    await tester.test(_test_name_is_the_header, "节点组名称占表头测试")
    await tester.test(_test_multiline_content_uses_br, "多行内容换行测试")
    await tester.test(_test_pipes_are_escaped, "内容竖线转义测试")
    await tester.test(_test_nodes_use_markdown_element, "节点 Markdown 元素发送测试")
    await tester.test(_test_markdown_element_selects_markdown_path, "消息元素选择 Markdown 路径测试")

    return tester
