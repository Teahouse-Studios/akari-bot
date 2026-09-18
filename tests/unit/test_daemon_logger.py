"""BotDaemon 日志过滤测试。"""

from bot import _is_daemon_log
from core.tester import Tester, func_case


def _test_daemon_log_filter():
    return (
        _is_daemon_log({"extra": {}})
        and _is_daemon_log({"extra": {"name": "BotDaemon"}})
        and not _is_daemon_log({"extra": {"name": "Server"}})
    )


@func_case
async def test_daemon_logger(tester: Tester):
    await tester.test(_test_daemon_log_filter, "pre-init 核心异常会进入 BotDaemon 日志")
    return tester
