"""bugtracker 空查询结果单元测试。"""

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
# 未关联任何版本的漏洞：versions 键在而值为空列表。MC-310702 即属此形
EMPTY_VERSIONS_RESULT = """{"issues": [{"key": "MC-310702", "fields": {"summary": "No version issue",
    "issuetype": {"name": "Bug"}, "status": {"name": "Open"}, "project": {"name": "Minecraft"},
    "versions": [], "fixVersions": []}}]}"""
# 单一版本与跨版本区间，用以守住两种文案分支
ONE_VERSION_RESULT = """{"issues": [{"key": "MC-2", "fields": {"summary": "One version",
    "issuetype": {"name": "Bug"}, "status": {"name": "Open"}, "project": {"name": "Minecraft"},
    "versions": [{"name": "1.21"}]}}]}"""
MULTI_VERSION_RESULT = """{"issues": [{"key": "MC-3", "fields": {"summary": "Many versions",
    "issuetype": {"name": "Bug"}, "status": {"name": "Open"}, "project": {"name": "Minecraft"},
    "versions": [{"name": "1.20"}, {"name": "1.21"}]}}]}"""


async def _build_session() -> MessageSession:
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|bugtracker",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(),
    )
    return MessageSession(session_info=session_info)


async def _query(response: str, mojira_id: str):
    msg = await _build_session()
    with (
        patch("modules.bugtracker.bugtracker.post_url", new=AsyncMock(return_value=response)),
        patch("modules.bugtracker.bugtracker.get_url", new=AsyncMock(return_value="{}")),
    ):
        return await bugtracker_get(msg, mojira_id)


async def _test_empty_result_returns_prompt():
    result, link = await _query(EMPTY_RESULT, "MCBE-1")
    return isinstance(result, I18NContextElement) and result.key == "bugtracker.message.get_failed" and link is None


async def _test_found_result_still_parsed():
    result, link = await _query(FOUND_RESULT, "MC-1")
    text = str(result)
    return "[MC-1]" in text and "Test issue" in text and link == "https://bugs.mojang.com/browse/MC/issues/MC-1"


async def _test_empty_versions_does_not_raise():
    result, link = await _query(EMPTY_VERSIONS_RESULT, "MC-310702")
    text = str(result)
    return "MC-310702" in text and "Version" not in text


async def _test_single_version_rendered():
    result, link = await _query(ONE_VERSION_RESULT, "MC-2")
    return "Version: 1.21" in str(result)


async def _test_version_range_rendered():
    result, link = await _query(MULTI_VERSION_RESULT, "MC-3")
    return "Versions: 1.20 ~ 1.21" in str(result)


@func_case
async def test_bugtracker_empty_result(tester: Tester):
    """bugtracker: 查询结果为空时的处理"""
    await tester.test(_test_empty_result_returns_prompt, "空结果转为提示文案")
    await tester.test(_test_found_result_still_parsed, "有结果时解析不受影响")
    await tester.test(_test_empty_versions_does_not_raise, "空版本列表不抛异常")
    await tester.test(_test_single_version_rendered, "单一版本文案")
    await tester.test(_test_version_range_rendered, "版本区间文案")
    return tester
