"""bugtracker 空查询结果单元测试。

Mojira 的搜索接口对不存在的项目或漏洞返回空的 issues 列表。旧实现以 issues[0] 触发
IndexError 来兜底，重构改为空列表时取 None 后，兜底分支即告失效，None 一路流到
"errorMessages" in load_json 处崩溃。用例即为守住空结果须转为提示文案这条边界。
"""

from unittest.mock import AsyncMock, patch

from core.builtins.message.elements import I18NContextElement
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.tester import func_case, Tester
from modules.bugtracker.bugtracker import bugtracker_get

EMPTY_RESULT = '{"issues": []}'
FOUND_RESULT = """{"issues": [{"key": "MC-1", "fields": {"summary": "Test issue",
    "issuetype": {"name": "Bug"}, "status": {"name": "Open"}, "project": {"name": "Minecraft"}}}]}"""


async def _build_session() -> MessageSession:
    """构造查询所需的最小会话。"""
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|bugtracker",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(),
    )
    return MessageSession(session_info=session_info)


async def _query(response: str, mojira_id: str):
    """在给定接口响应下跑一遍查询。

    :param response: 搜索接口返回的 JSON 文本。
    :param mojira_id: 漏洞编号。
    :return: bugtracker_get 的返回值。
    """
    msg = await _build_session()
    with (
        patch("modules.bugtracker.bugtracker.post_url", new=AsyncMock(return_value=response)),
        patch("modules.bugtracker.bugtracker.get_url", new=AsyncMock(return_value="{}")),
    ):
        return await bugtracker_get(msg, mojira_id)


async def _test_empty_result_returns_prompt():
    """空结果应转为提示文案而非抛出异常。"""
    result, link = await _query(EMPTY_RESULT, "MCBE-1")
    return isinstance(result, I18NContextElement) and result.key == "bugtracker.message.get_failed" and link is None


async def _test_found_result_still_parsed():
    """有结果时的解析路径不应受空结果处理影响。"""
    result, link = await _query(FOUND_RESULT, "MC-1")
    text = str(result)
    return "[MC-1]" in text and "Test issue" in text and link == "https://bugs.mojang.com/browse/MC/issues/MC-1"


@func_case
async def test_bugtracker_empty_result(tester: Tester):
    """bugtracker: 查询结果为空时的处理"""
    await tester.test(_test_empty_result_returns_prompt, "空结果转为提示文案")
    await tester.test(_test_found_result_still_parsed, "有结果时解析不受影响")
    return tester
