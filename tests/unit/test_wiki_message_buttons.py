"""wiki 结果消息的按钮挂载测试 - 只挂按钮的空消息不应被发出。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
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


async def _run_query(page: PageInfo, session: MessageSession) -> tuple[list, list]:
    sent = []
    waits = []

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
        patch.object(WikiLib, "parse_page_info", new=AsyncMock(return_value=page)),
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=_target())),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch("modules.wiki.wiki._start_background_with_release", new=_run_background),
        patch.object(MessageSession, "hold", new=AsyncMock()),
        patch.object(MessageSession, "release", new=AsyncMock()),
        patch.object(MessageSession, "send_message", new=_send_message),
        patch.object(MessageSession, "finish", new=_finish),
        patch.object(MessageSession, "wait_next_message", new=_wait_next_message),
    ):
        try:
            await query_pages(session, title="示例条目")
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
    prompt, kwargs = waits[0]
    keys = [element.key for element in prompt if isinstance(element, I18NContextElement)]
    rows = kwargs.get("possibly_choices") or []
    return (
        keys == ["wiki.message.not_found.autofix.choice"]
        and [next(iter(row)) for row in rows] == SUGGESTIONS
        and [next(iter(row.values())) for row in rows] == ["1", "2", "3", "4", "5"]
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
    prompt, kwargs = waits[0]
    keys = [element.key for element in prompt if isinstance(element, I18NContextElement)]
    rows = kwargs.get("possibly_choices") or []
    return (
        keys == ["wiki.message.not_found.autofix.confirm", "message.wait.confirm.prompt.button"]
        and len(rows) == 1
        and list(rows[0].values()) == [confirm_command[0], "no"]
    )


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
    sent, waits = await _run_query(page, session)

    if len(sent) != 1 or waits:
        return False
    frames = [element for element in sent[0] if isinstance(element, ButtonFrameElement)]
    urls = [element.url for element in sent[0] if isinstance(element, URLElement)]
    buttons = [(button.show, button.value) for frame in frames for row in frame.rows for button in row.buttons]
    return urls == [ARTICLE] and buttons == [
        (Locale("zh_cn").t("wiki.message.render.action.button"), "wiki_render_preview"),
        (Locale("zh_cn").t("wiki.message.render.action.delete"), "wiki_render_delete"),
    ]


@func_case
async def test_wiki_message_buttons(tester: Tester):
    """wiki 消息按钮挂载测试"""
    await tester.test(_test_not_found_sends_no_button_only_message, "多个候选时不发出空按钮消息")
    await tester.test(_test_single_suggestion_sends_no_button_only_message, "单个候选时不发出空按钮消息")
    await tester.test(_test_found_page_keeps_render_buttons, "正常页面照常挂渲染按钮")

    return tester
