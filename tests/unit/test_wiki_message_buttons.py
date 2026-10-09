"""wiki 结果消息的按钮挂载测试 - 只挂按钮的空消息不应被发出。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ButtonFrameElement, I18NContextElement, URLElement
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import confirm_command
from core.constants.exceptions import SessionFinished
from core.i18n import Locale
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


async def _test_found_page_keeps_render_buttons():
    page = PageInfo(
        info=WikiInfo(api=API, realurl=ARTICLE, is_allowed=True),
        title="示例页面",
        link=ARTICLE,
        desc="页面摘要",
        status=True,
        renderable=True,
    )
    session = MessageSession(session_info=await _session_info("wiki-found-buttons"))
    render_preview = AsyncMock(return_value=MessageChain.assign("rendered preview"))
    sent, waits = await _run_query(page, session, render_preview)

    if len(sent) != 1 or waits or render_preview.await_count != 1:
        return False
    frames = [element for element in sent[0] if isinstance(element, ButtonFrameElement)]
    urls = [element.url for element in sent[0] if isinstance(element, URLElement)]
    buttons = [(button.show, button.value) for frame in frames for row in frame.rows for button in row.buttons]
    return (
        urls == [ARTICLE]
        and render_preview.await_args.args[1][0]["link"] == ARTICLE
        and render_preview.await_args.args[1][0]["wiki_info"] is page.info
        and render_preview.await_args.args[1][0]["title"] == page.title
        and buttons
        == [
            (Locale("zh_cn").t("wiki.message.render.action.button"), "wiki_render_preview"),
            (Locale("zh_cn").t("wiki.message.render.action.delete"), "wiki_render_delete"),
        ]
    )


@func_case
async def test_wiki_message_buttons(tester: Tester):
    """wiki 消息按钮挂载测试"""
    await tester.test(_test_not_found_sends_no_button_only_message, "多个候选时不发出空按钮消息")
    await tester.test(_test_single_suggestion_sends_no_button_only_message, "单个候选时不发出空按钮消息")
    await tester.test(_test_multiple_redirects_build_choice_rows, "多个重定向候选时构造按钮行")
    await tester.test(_test_found_page_keeps_render_buttons, "正常页面照常挂渲染按钮")

    return tester
