"""wiki 结果消息的交互与样式设置测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ButtonFrameElement, CardElement, I18NContextElement, ImageElement, URLElement
from core.builtins.parser.command import CommandParser
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import confirm_command
from core.constants.exceptions import InvalidCommandFormatError, SessionFinished
from core.database.models import TargetUnionInfo
from core.i18n import Locale
from core.loader import ModulesManager
from core.tester import func_case, Tester
from modules.wiki.utils.wikilib import PageInfo, WikiInfo, WikiLib
from modules.wiki.wiki import query_pages


API = "https://example.com/api.php"
ARTICLE = "https://example.com/wiki/示例页面"
SUGGESTIONS = ["示例条目 1", "示例条目 2", "示例条目 3", "示例条目 4", "示例条目 5"]


def _is_button_only(message_chain) -> bool:
    elements = list(message_chain)
    return bool(elements) and all(isinstance(element, ButtonFrameElement) for element in elements)


async def _session_info(tag: str) -> SessionInfo:
    # 未找到分支会读取 target_union_info.target_data，故走 assign 以贴近真实会话。
    return await SessionInfo.assign(
        target_id=f"TEST|Group|{tag}",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(support_button=True, support_image=True, support_wait=True),
    )


def _target() -> SimpleNamespace:
    return SimpleNamespace(api_link=API, interwikis={}, headers={}, prefix=None)


async def _run_query(
    page: PageInfo | list[PageInfo],
    session: MessageSession,
    render_preview: AsyncMock | None = None,
    title: str | list[str] = "示例条目",
) -> tuple[list, list]:
    sent = []
    waits = []
    pages = page if isinstance(page, list) else [page]
    parse_result = AsyncMock(side_effect=pages) if len(pages) > 1 else AsyncMock(return_value=pages[0])

    async def _send_message(self, message_chain=None, **kwargs):
        sent.append(message_chain)
        return SimpleNamespace(message_id=[f"m{len(sent)}"])

    async def _finish(self, message_chain=None, **kwargs):
        sent.append(message_chain)
        raise SessionFinished

    async def _wait_next_message(self, message_chain=None, **kwargs):
        waits.append((message_chain, kwargs))
        # 用户回复了无法识别的文本，等待链路按取消处理，不再发起新查询。
        return SimpleNamespace(as_display=lambda text_only=False: "取消")

    async def _run_background(_session, awaitable_factory, **_kwargs):
        await awaitable_factory()

    with (
        patch.object(Bot.Info, "web_render_status", True),
        patch.object(WikiLib, "parse_page_info", new=parse_result),
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=_target())),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch(
            "modules.wiki.wiki._render_preview_items",
            new=render_preview or AsyncMock(return_value=MessageChain.assign("rendered preview")),
        ),
        patch("modules.wiki.wiki.generate_screenshot", new=AsyncMock(return_value=["/tmp/wiki-preview.png"])),
        patch("modules.wiki.wiki._start_background_with_release", new=_run_background),
        patch.object(MessageSession, "hold", new=AsyncMock()),
        patch.object(MessageSession, "release", new=AsyncMock()),
        patch.object(MessageSession, "send_message", new=_send_message),
        patch.object(MessageSession, "finish", new=_finish),
        patch.object(MessageSession, "wait_next_message", new=_wait_next_message),
    ):
        try:
            await query_pages(session, title=title)
        except SessionFinished:
            pass
    return sent, waits


async def _test_not_found_sends_no_button_only_message():
    page = PageInfo(
        info=WikiInfo(api=API, realurl=ARTICLE, is_allowed=True),
        title=SUGGESTIONS[0],
        before_title="示例条目",
        status=False,
        possible_research_title=list(SUGGESTIONS),
    )
    session = MessageSession(session_info=await _session_info("wiki-not-found-buttons"))
    sent, waits = await _run_query(page, session)

    if any(_is_button_only(chain) for chain in sent):
        return False
    if len(waits) != 1:
        return False
    prompt, _ = waits[0]
    keys = [element.key for element in prompt if isinstance(element, I18NContextElement)]
    rows = [
        [(button.show, button.value) for button in row.buttons]
        for frame in prompt
        if isinstance(frame, ButtonFrameElement)
        for row in frame.rows
    ]
    close_label = session.t("wiki.message.render.action.delete")
    return (
        keys == ["wiki.message.not_found.autofix.choice"]
        and [show for row in rows for show, _ in row] == SUGGESTIONS[:-1] + [SUGGESTIONS[-1], close_label]
        and [value for row in rows for _, value in row] == ["1", "2", "3", "4", "5", "close"]
        and rows[-1] == [(SUGGESTIONS[-1], "5"), (close_label, "close")]
    )


async def _test_single_suggestion_sends_no_button_only_message():
    page = PageInfo(
        info=WikiInfo(api=API, realurl=ARTICLE, is_allowed=True),
        title=SUGGESTIONS[0],
        before_title="示例条目",
        status=False,
        possible_research_title=[SUGGESTIONS[0]],
    )
    session = MessageSession(session_info=await _session_info("wiki-single-suggestion"))
    sent, waits = await _run_query(page, session)

    if any(_is_button_only(chain) for chain in sent):
        return False
    if len(waits) != 1:
        return False
    prompt, _ = waits[0]
    keys = [element.key for element in prompt if isinstance(element, I18NContextElement)]
    rows = [
        [button.value for button in row.buttons]
        for frame in prompt
        if isinstance(frame, ButtonFrameElement)
        for row in frame.rows
    ]
    return keys == ["wiki.message.not_found.autofix.confirm", "message.wait.confirm.prompt.button"] and rows == [
        [confirm_command[0], "no"]
    ]


async def _test_multiple_redirects_build_choice_rows():
    pages = [
        PageInfo(
            info=WikiInfo(api=API, realurl=ARTICLE, is_allowed=True),
            title=f"重定向条目 {index}",
            before_title=f"原条目 {index}",
            status=False,
            possible_research_title=[f"重定向条目 {index}"],
        )
        for index in range(1, 3)
    ]
    session = MessageSession(session_info=await _session_info("wiki-multi-redirect"))
    sent, waits = await _run_query(pages, session, title=[page.title for page in pages])

    if any(_is_button_only(chain) for chain in sent):
        return False
    if len(waits) != 1:
        return False
    prompt, _ = waits[0]
    rows = [
        [(button.show, button.value) for button in row.buttons]
        for frame in prompt
        if isinstance(frame, ButtonFrameElement)
        for row in frame.rows
    ]
    return rows == [
        [("重定向条目 1", "1"), ("重定向条目 2", "2")],
    ]


async def _test_found_page_uses_compatible_preview_mode():
    page = PageInfo(
        info=WikiInfo(api=API, realurl=ARTICLE, is_allowed=True),
        title="示例页面",
        link=ARTICLE,
        desc="页面摘要",
        status=True,
        renderable=True,
    )
    for style, render_mode in (
        ("text", "button"),
        ("card", None),
        ("card", "button"),
        ("card", "auto"),
        ("card", "off"),
    ):
        session_info = await _session_info(f"wiki-found-buttons-{style}-{render_mode}")
        if render_mode is not None:
            session_info.target_union_info.target_data["wiki_render_mode"] = render_mode
        if style == "card":
            session_info.client_name = "QQBot"
            session_info.support_card = True
            session_info.target_union_info.target_data["wiki_message_style"] = "card"
        session = MessageSession(session_info=session_info)
        render_preview = AsyncMock(return_value=MessageChain.assign("rendered preview"))
        sent, waits = await _run_query(page, session, render_preview)

        assert not waits
        frames = [element for element in sent[0] if isinstance(element, ButtonFrameElement)]
        urls = [element.url for element in sent[0] if isinstance(element, URLElement)]
        cards = [element for element in sent[0] if isinstance(element, CardElement)]
        if style == "card":
            assert len(cards) == 1 and cards[0].url == ARTICLE and not urls
            assert not any(MessageChain.assign(chain).contains(ButtonFrameElement) for chain in sent)
            if render_mode == "off":
                assert len(sent) == 1
            else:
                assert len(sent) == 2 and MessageChain.assign(sent[1]).contains(ImageElement)
        else:
            assert urls == [ARTICLE] and not cards
            assert len(sent) == 1 and render_preview.await_count == 1
            buttons = [(button.show, button.value) for frame in frames for row in frame.rows for button in row.buttons]
            assert buttons == [
                (Locale("zh_cn").t("wiki.message.render.action.button"), "wiki_render_preview"),
                (Locale("zh_cn").t("wiki.message.render.action.delete"), "wiki_render_delete"),
            ]
    return True


async def _test_style_command_persists_and_rejects_invalid_modes():
    session = MessageSession(
        session_info=await SessionInfo.assign(
            target_id="QQBot|Group|wiki-message-style",
            target_from="QQBot|Group",
            client_name="QQBot",
            sender_id="QQBot|wiki-style-admin",
            features=Features(support_button=True, support_card=True),
        )
    )
    module = ModulesManager.return_modules_list()["wiki"]
    parser = CommandParser(module, ["~"], module_name="wiki", msg=session, include_restricted=True)
    sent = []

    async def finish(self, message_chain=None, **kwargs):
        sent.append(MessageChain.assign(message_chain))
        raise SessionFinished

    with patch.object(MessageSession, "finish", new=finish):
        for mode, expected, message_key in [
            ("CARD", "card", "wiki.message.style.card"),
            ("text", "text", "wiki.message.style.text"),
            ("plain", "text", "wiki.message.style.invalid"),
            ("invalid", "text", "wiki.message.style.invalid"),
        ]:
            command, args = parser.parse(f"wiki style {mode}")
            try:
                await command.function(session, args["<mode>"])
            except SessionFinished:
                pass
            saved = await TargetUnionInfo.get(union_id=session.session_info.target_union_id)
            assert saved.target_data["wiki_message_style"] == expected
            assert any(isinstance(item, I18NContextElement) and item.key == message_key for item in sent[-1])
            if expected == "card":
                text = sent[-1].as_sendable(session.session_info).to_str()
                assert "不支持按钮" in text and "auto" in text
    return True


async def _test_style_command_visibility_matches_card_support():
    module = ModulesManager.return_modules_list()["wiki"]
    for target_from, client_name, is_admin, available in [
        ("QQBot|Group", "QQBot", True, True),
        ("QQBot|C2C", "QQBot", True, True),
        ("QQBot|Guild", "QQBot", True, False),
        ("QQBot|Direct", "QQBot", True, False),
        ("QQ|Group", "QQ", True, False),
        ("Discord|Channel", "Discord", True, False),
        ("QQBot|Group", "QQBot", False, True),
    ]:
        session = MessageSession(
            session_info=SessionInfo(
                target_id=f"{target_from}|wiki-style-visibility",
                target_from=target_from,
                client_name=client_name,
                sender_id=f"{client_name}|wiki-style-viewer",
                sender_union_info=SimpleNamespace(superuser=False),
                locale=Locale("zh_cn"),
            )
        )
        parser = CommandParser(module, ["~"], module_name="wiki", msg=session, is_superuser=False, is_admin=is_admin)
        assert ("~wiki style <mode>" in parser.return_formatted_help_doc()) == (available and is_admin)
        parser = CommandParser(module, ["~"], module_name="wiki", msg=session, include_restricted=True)
        try:
            _, args = parser.parse("wiki style card")
            matched = args.get("<mode>") == "card"
        except InvalidCommandFormatError:
            matched = False
        assert matched == available
    return True


@func_case
async def test_wiki_message_buttons(tester: Tester):
    """wiki 结果消息交互与样式设置测试"""
    await tester.test(_test_not_found_sends_no_button_only_message, "多个候选时不发出空按钮消息")
    await tester.test(_test_single_suggestion_sends_no_button_only_message, "单个候选时不发出空按钮消息")
    await tester.test(_test_multiple_redirects_build_choice_rows, "多个重定向候选时构造按钮行")
    await tester.test(
        _test_found_page_uses_compatible_preview_mode, "卡片样式自动发送预览且保留关闭设置，文字样式支持按钮"
    )
    await tester.test(_test_style_command_persists_and_rejects_invalid_modes, "Wiki 样式设置持久化且拒绝非法参数")
    await tester.test(_test_style_command_visibility_matches_card_support, "Wiki 样式命令仅在支持卡片的 QQBot 场景显示")

    return tester
