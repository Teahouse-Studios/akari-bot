"""status 模块的 Markdown 排版与进程行测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.queue.diagnostics import DAEMON_LABEL, ProcessUnavailable, ProcessUsage
from core.tester import Tester, func_case
from modules.core.common_tools.ping import _build_process_usage_lines


def _msg(support_markdown: bool):
    return SimpleNamespace(
        session_info=SessionInfo(
            target_id="TEST|Console|ping",
            target_from="TEST",
            client_name="TEST",
            support_markdown=support_markdown,
            locale=Locale("zh_cn"),
        )
    )


def _patch_usage(usages, failures):
    return patch(
        "modules.core.common_tools.ping.gather_process_usage",
        new=AsyncMock(return_value=(usages, failures)),
    )


async def _test_process_usage_lines_use_status_keys():
    usages = [ProcessUsage(name=DAEMON_LABEL, pid=12, memory=100 * 1024 * 1024, metric="RSS")]
    failures = [ProcessUnavailable(name="jobqueue-hub", reason="timeout")]
    with _patch_usage(usages, failures):
        lines = await _build_process_usage_lines(_msg(True))
    if len(lines) != 2:
        return False
    usage_line, failure_line = lines
    # 语言键缺失时会回落为键名或提示，故一律断言不含 "core.message"。
    return (
        "core.message" not in usage_line
        and "12" in usage_line
        and "100M" in usage_line
        and "RSS" in usage_line
        and DAEMON_LABEL not in usage_line
        and "core.message" not in failure_line
        and "jobqueue-hub" in failure_line
        and "timeout" in failure_line
    )


async def _test_process_usage_lines_absent_without_data():
    with _patch_usage([], []):
        return await _build_process_usage_lines(_msg(True)) == []


@func_case
async def test_status(tester: Tester):
    """status: Markdown 能力选择代码块或纯文本。"""
    await tester.test(_test_process_usage_lines_use_status_keys, "status 进程行本地化测试")
    await tester.test(_test_process_usage_lines_absent_without_data, "status 无进程数据静默测试")
    return tester
