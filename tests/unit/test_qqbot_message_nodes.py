"""消息节点在 QQBot 上的表格化测试。

平台没有合并转发，节点此前只能整体转成图片。改为摊平成一张 markdown 表后，编号与内容上下
相邻——编号在上一格、内容在正下方那一格，表头留给节点组名称。与帮助的表格同一思路：高度封顶，
节点变多时由列数吸收。

两处易错：节点内容常为多行（wiki 的近期更改每条含标题、摘要、链接与时间戳），单元格容不下
换行，须换成 <br>；摊平后的表格是纯文本，若不强制走 markdown 路径，会被判为「不需要
markdown」而退回纯文本，表格标记原样露出。
"""

from unittest.mock import patch

from botpy.message import GroupMessage

import bots.qqbot.context as qqbot_context
from bots.qqbot.context import MESSAGE_NODES_MAX_ROWS, QQBotContextManager, nodes_to_table
from bots.qqbot.features import features as qqbot_features
from bots.qqbot.config import QQBotConfig
from bots.qqbot.info import target_group_prefix
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.tester import func_case, Tester

BACKSLASH = chr(92)


def _make_session() -> SessionInfo:
    """构造一个用于节点转换的会话。

    :return: 会话信息。
    """
    return SessionInfo(
        target_id=f"{target_group_prefix}|fake_group",
        sender_id="QQBot|1",
        target_from=target_group_prefix,
        client_name="QQBot",
        session_id="nodes-table",
        support_markdown=True,
    )


def _make_nodes(count: int, text: str = "内容") -> MessageNodes:
    """构造若干节点。

    :param count: 节点数量。
    :param text: 每个节点的文本。
    :return: 消息节点。
    """
    return MessageNodes.assign([MessageChain.assign(Plain(f"{text}{i}")) for i in range(count)], name="标题")


def _unescaped_pipes(line: str) -> int:
    """数出未转义的竖线：单元格内被反斜杠转义的竖线是字面量，不构成列分隔。

    :param line: 一行文本。
    :return: 未转义的竖线数量。
    """
    count, prev = 0, ""
    for char in line:
        if char == "|" and prev != BACKSLASH:
            count += 1
        prev = char
    return count


def _test_feature_follows_markdown_config() -> bool:
    """节点支持须跟随 qq_use_markdown：表格只在 markdown 路径上成立"""
    if qqbot_features.support_handle_message_nodes is not QQBotConfig.qq_use_markdown:
        Logger.error("QQBot should tie support_handle_message_nodes to qq_use_markdown")
        return False
    return True


def _test_table_shape() -> bool:
    """测试高度封顶，节点变多时由列数吸收

    一「行」实为两行：一行编号、一行内容。上限现为一对，故不论多少节点都只有一对数据行，
    列数即节点数。
    """
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
    """测试各行列数一致，末对补空单元格"""
    session_info = _make_session()
    for count in range(1, 40):
        lines = nodes_to_table(session_info, _make_nodes(count)).split("\n")
        widths = {_unescaped_pipes(line) for line in lines}
        if len(widths) != 1:
            Logger.error(f"{count} nodes produced ragged rows: {lines}")
            return False
    return True


def _test_index_sits_above_content() -> bool:
    """测试编号在上一行、内容在正下方那一行，且编号自 1 起随节点顺序递增

    按结构遍历而非比对固定字符串：列数随高度上限而变，写死行内容会在调整上限时失效。
    """
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
    """测试节点组名称占据表头"""
    lines = nodes_to_table(_make_session(), _make_nodes(2)).split("\n")
    if not lines[0].startswith("| 标题 |"):
        Logger.error(f"The node group name should head the table, got {lines[0]!r}")
        return False
    return True


def _test_multiline_content_uses_br() -> bool:
    """测试多行内容换成 <br>

    单元格容不下换行，放任换行会把表格劈成两半。
    """
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
    """测试内容中的竖线被转义，否则该行会拆出多余的列"""
    nodes = MessageNodes.assign([MessageChain.assign(Plain("甲|乙"))], name="标题")
    table = nodes_to_table(_make_session(), nodes)
    if f"甲{BACKSLASH}|乙" not in table:
        Logger.error(f"Pipes inside a cell should be escaped, got {table!r}")
        return False
    return True


class _FakeGroupMessage(GroupMessage):
    """替身群消息，绕过 SDK 的构造流程，仅记录发送时收到的参数。"""

    def __init__(self):
        self.id = "source-message"
        self.group_openid = "fake_group"
        self.message_scene = None
        self.reply_kwargs: list[dict] = []

    async def reply(self, **kwargs):
        self.reply_kwargs.append(kwargs)
        return {"id": "sent-1"}


async def _test_nodes_force_markdown() -> bool:
    """测试节点表格强制走 markdown 路径

    摊平后的表格是纯文本，不强制的话会被判为「不需要 markdown」而退回纯文本，
    表格标记原样露出。
    """
    session_id = "nodes-send"
    session_info = _make_session()
    session_info.session_id = session_id
    ctx = _FakeGroupMessage()
    QQBotContextManager.context[session_id] = ctx
    try:
        with patch.object(qqbot_context, "qq_use_markdown", True):
            await QQBotContextManager.send_message(session_info, _make_nodes(3), quote=False)
    finally:
        QQBotContextManager.context.pop(session_id, None)

    if not ctx.reply_kwargs:
        Logger.error("Sending message nodes should reach the platform")
        return False
    sent = ctx.reply_kwargs[0]
    if "markdown" not in sent:
        Logger.error(f"A node table must be sent as markdown, got {sorted(sent)}")
        return False
    return True


async def _test_force_markdown_flag_from_module() -> bool:
    """测试模块经 force_markdown 声明后，全为纯文本的消息也走 markdown

    纯正则模块的帮助表格里没有可点击命令，整条消息全是纯文本，平台默认会退回纯文本发送，
    表格标记原样露出。该标志正是为此而设。
    """
    table = "| 正则 |  |\n|---|---|\n| a | b |"
    for declared, expect_markdown in ((True, True), (False, False)):
        session_id = f"force-md-{declared}"
        session_info = _make_session()
        session_info.session_id = session_id
        session_info.tmp = {"force_markdown": "true" if declared else ""}
        ctx = _FakeGroupMessage()
        QQBotContextManager.context[session_id] = ctx
        try:
            with patch.object(qqbot_context, "qq_use_markdown", True):
                await QQBotContextManager.send_message(session_info, MessageChain.assign(Plain(table)), quote=False)
        finally:
            QQBotContextManager.context.pop(session_id, None)
        if not ctx.reply_kwargs:
            Logger.error(f"Sending should reach the platform (declared={declared})")
            return False
        sent_markdown = "markdown" in ctx.reply_kwargs[0]
        if sent_markdown is not expect_markdown:
            Logger.error(
                f"force_markdown={declared} should send as markdown={expect_markdown}, got {sorted(ctx.reply_kwargs[0])}"
            )
            return False
    return True


@func_case
async def test_qqbot_message_nodes(tester: Tester):
    """bots.qqbot.context: 消息节点表格化测试"""
    await tester.test(_test_feature_follows_markdown_config, "节点支持跟随配置测试")
    await tester.test(_test_table_shape, "表格行列数测试")
    await tester.test(_test_rows_are_uniform, "表格列数齐平测试")
    await tester.test(_test_index_sits_above_content, "编号在上内容在下测试")
    await tester.test(_test_name_is_the_header, "节点组名称占表头测试")
    await tester.test(_test_multiline_content_uses_br, "多行内容换行测试")
    await tester.test(_test_pipes_are_escaped, "内容竖线转义测试")
    await tester.test(_test_nodes_force_markdown, "节点强制走 markdown 测试")
    await tester.test(_test_force_markdown_flag_from_module, "模块声明强制 markdown 测试")

    return tester
