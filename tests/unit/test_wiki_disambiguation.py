"""Wiki 消歧义页面识别、链接操作化与分平台长度处理测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from botpy.message import GroupMessage

import bots.qqbot.context as qqbot_context
from bots.qqbot.context import QQBotContextManager
from bots.qqbot.info import target_group_prefix
from core.builtins.message.elements import ActionTextElement, MarkdownElement
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import func_case, Tester
from modules.wiki.utils.disambiguation import (
    DISAMBIGUATION_MAX_BLOCKS,
    DisambiguationBlock,
    DisambiguationPart,
    parse_disambiguation_html,
)
from modules.wiki.utils.wikilib import WikiInfo, WikiLib
from modules.wiki.wiki import _build_disambiguation_output

PARTICLE_HTML = """
<div class="mw-content-ltr mw-parser-output">
  <p>粒子（Particle）是特定事件发生时出现的图形效果。</p>
  <div class="msgbox"><a href="https://zh.minecraft.wiki/w/Draft:%E7%B2%92%E5%AD%90">草稿</a></div>
  <p>它可以指：</p>
  <ul>
    <li><a href="/w/Java%E7%89%88%E7%B2%92%E5%AD%90" title="Java版粒子">Java版粒子</a></li>
    <li><a href="/w/%E5%9F%BA%E5%B2%A9%E7%89%88%E7%B2%92%E5%AD%90" title="基岩版粒子">基岩版粒子</a></li>
  </ul>
  <dl><dt>命令</dt></dl>
  <ul><li>/<a href="/w/%E5%91%BD%E4%BB%A4/particle" title="命令/particle">particle</a></li></ul>
  <div class="footnote disambig">这是一个<a class="external" href="https://example.com/">消歧义</a>页面。</div>
</div>
"""


def _msg(client_name: str, *, table: bool, action: bool = True):
    return SimpleNamespace(
        session_info=SimpleNamespace(
            client_name=client_name,
            support_markdown_table=table,
            support_action_text=action,
            prefixes=["~"],
            locale=Locale("zh_cn"),
        )
    )


def _long_page():
    return SimpleNamespace(
        disambiguation_blocks=[
            *[
                DisambiguationBlock([DisambiguationPart(f"候选 {index}", f"页面 {index}")])
                for index in range(DISAMBIGUATION_MAX_BLOCKS + 2)
            ],
            DisambiguationBlock([DisambiguationPart("矿车是一类可以在铁轨上行驶的实体，包括：")]),
            DisambiguationBlock([DisambiguationPart("Minecraft")], is_title=True),
        ]
    )


class _FakeGroupMessage(GroupMessage):
    def __init__(self):
        self.id = "source-message"
        self.group_openid = "wiki-disambiguation"
        self.message_scene = None


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def send_markdown(self, target, content, keyboard=None):
        self.calls.append({"content": content, "keyboard": keyboard})
        return {"id": "sent-1"}


async def _test_particle_html_keeps_internal_targets():
    blocks = parse_disambiguation_html(PARTICLE_HTML, "https://zh.minecraft.wiki/")
    targets = [part.target for block in blocks for part in block.parts if part.target]
    return (
        [block.text for block in blocks]
        == [
            "粒子（Particle）是特定事件发生时出现的图形效果。",
            "草稿",
            "它可以指：",
            "Java版粒子",
            "基岩版粒子",
            "命令",
            "/particle",
        ]
        and targets == ["Draft:粒子", "Java版粒子", "基岩版粒子", "命令/particle"]
        and blocks[5].is_title
    )


async def _test_wikilib_marks_pageprops_disambiguation():
    wiki = WikiLib("https://zh.minecraft.wiki/api.php")
    wiki.wiki_info = WikiInfo(
        api="https://zh.minecraft.wiki/api.php",
        articlepath="https://zh.minecraft.wiki/w/$1",
        script="https://zh.minecraft.wiki/w/index.php",
        extensions=["TextExtracts"],
    )
    wiki.fixup_wiki_info = AsyncMock()
    wiki.get_page_body_class = AsyncMock(return_value=[])
    wiki.get_json = AsyncMock(
        side_effect=[
            {
                "query": {
                    "pages": {
                        "1": {
                            "title": "粒子",
                            "fullurl": "https://zh.minecraft.wiki/w/粒子",
                            "templates": [],
                            "extract": "截断的摘要",
                            "pageprops": {"disambiguation": ""},
                        }
                    }
                }
            },
            {"parse": {"text": {"*": PARTICLE_HTML}}},
        ]
    )

    page = await wiki.parse_page_info("粒子")
    return page.is_disambiguation and len(page.disambiguation_blocks) == 7 and wiki.get_json.await_count == 2


async def _test_short_page_uses_action_text():
    page = SimpleNamespace(disambiguation_blocks=parse_disambiguation_html(PARTICLE_HTML, "https://zh.minecraft.wiki/"))
    output = _build_disambiguation_output(_msg("QQBot", table=True), page, "")
    actions = [element for element in output if isinstance(element, ActionTextElement)]
    return [element.text.text for element in actions] == [
        "~wiki Draft:粒子",
        "~wiki Java版粒子",
        "~wiki 基岩版粒子",
        "~wiki 命令/particle",
    ] and not output.contains(MarkdownElement)


async def _test_long_qqbot_page_uses_complete_table():
    output = _build_disambiguation_output(_msg("QQBot", table=True), _long_page(), "mc:")
    actions = [element for element in output if isinstance(element, ActionTextElement)]
    return (
        output.contains(MarkdownElement)
        and len(actions) == DISAMBIGUATION_MAX_BLOCKS + 2
        and actions[-1].text.text == f"~wiki mc:页面 {DISAMBIGUATION_MAX_BLOCKS + 1}"
    )


async def _test_long_qqbot_payload_keeps_table_and_actions():
    session_id = "wiki-disambiguation-table"
    session_info = SessionInfo(
        target_id=f"{target_group_prefix}|wiki-disambiguation",
        target_from=target_group_prefix,
        client_name="QQBot",
        sender_id="QQBot|1",
        session_id=session_id,
        locale=Locale("zh_cn"),
        prefixes=["~"],
        support_markdown=True,
        support_markdown_table=True,
        support_action_text=True,
    )
    output = _build_disambiguation_output(SimpleNamespace(session_info=session_info), _long_page(), "")
    client = _FakeClient()
    QQBotContextManager.context[session_id] = _FakeGroupMessage()
    try:
        with (
            patch.object(qqbot_context, "qq_use_markdown", True),
            patch.object(QQBotContextManager, "client", client),
        ):
            await QQBotContextManager.send_message(session_info, output, quote=False)
    finally:
        QQBotContextManager.context.pop(session_id, None)
    content = client.calls[0]["content"]
    table_lines = content.splitlines()
    return (
        "| 可能指 |" in content
        and content.count("<qqbot-cmd-input ") == DISAMBIGUATION_MAX_BLOCKS + 2
        and "Minecraft" not in content
        and all(line.startswith("|") and line.endswith("|") and line.count("|") == 3 for line in table_lines)
        and not any(line == "|" for line in table_lines)
    )


async def _test_long_other_page_uses_render_only():
    output = _build_disambiguation_output(_msg("Discord", table=False), _long_page(), "")
    return not output


async def _test_qqbot_without_markdown_table_uses_render_only():
    output = _build_disambiguation_output(_msg("QQBot", table=False, action=False), _long_page(), "")
    return not output


@func_case
async def test_wiki_disambiguation(tester: Tester):
    await tester.test(_test_particle_html_keeps_internal_targets, "粒子消歧义样本保留内部目标")
    await tester.test(_test_wikilib_marks_pageprops_disambiguation, "pageprops 消歧义识别与完整正文解析")
    await tester.test(_test_short_page_uses_action_text, "短消歧义页使用 ActionText")
    await tester.test(_test_long_qqbot_page_uses_complete_table, "QQBot 长消歧义页使用完整 Markdown 表格")
    await tester.test(_test_long_qqbot_payload_keeps_table_and_actions, "QQBot 表格载荷保留全部 ActionText")
    await tester.test(_test_long_other_page_uses_render_only, "其他平台长消歧义页仅使用页面渲染")
    await tester.test(_test_qqbot_without_markdown_table_uses_render_only, "QQBot 关闭 Markdown 后仅使用页面渲染")
    return tester
