"""ping 在 Markdown 平台上的引用块排版测试。"""

from types import SimpleNamespace

from core.i18n import Locale
from core.queue.diagnostics import ProcessUnavailable, ProcessUsage
from core.tester import func_case, Tester
from modules.core.utils import _PingStatus, _build_ping_detail_markdown, _build_ping_simple_markdown


def _msg(*, markdown: bool):
    return SimpleNamespace(
        session_info=SimpleNamespace(
            locale=Locale("zh_cn"),
            support_markdown=markdown,
        )
    )


def _status():
    return _PingStatus(
        system_boot_time="2026-09-13 10:00:00 +08:00",
        bot_running_time="01:02:03",
        python_version="3.13.0",
        web_render_status="ok",
        jobqueue_backend="local",
        client_name="Discord",
        command_parsed=12,
        message_parsed=34,
        cpu_brand="AMD | Ryzen",
        cpu_percent=12.5,
        ram=16384,
        ram_percent=50.0,
        swap=2048,
        swap_percent=25.0,
        disk=100,
        disk_total=500,
        disk_percent=20.0,
    )


def _test_simple_markdown_uses_quote_block():
    text = _build_ping_simple_markdown(
        _msg(markdown=True),
        bot_running_time="01:02:03",
        cpu_percent=12.5,
        ram_percent=50.0,
        disk_percent=20.0,
    ).text
    return (
        text.startswith("> **Pong!**")
        and "> 机器人已运行：`01:02:03` · 处理器使用率：`12.5%`" in text
        and "> 内存使用率：`50.0%` · 磁盘使用率：`20.0%`" in text
        and "|" not in text
        and len(text) < 160
    )


def _test_detail_markdown_uses_sections_and_process_list():
    text = _build_ping_detail_markdown(
        _msg(markdown=True),
        _status(),
        [ProcessUsage("QQ", 42, 10 * 1024 * 1024, "USS")],
        [ProcessUnavailable("Discord", "timeout")],
    ).text
    return (
        text.startswith("> **Pong!**")
        and "> **系统**" in text
        and "> **资源**" in text
        and "> **各进程内存占用**" in text
        and "AMD | Ryzen" in text
        and "> QQ（PID 42）：10M（USS）" in text
        and "> Discord：不可用（timeout）" in text
        and "| --- |" not in text
        and len(text) < 600
    )


def _test_detail_markdown_keeps_process_list_compact():
    text = _build_ping_detail_markdown(
        _msg(markdown=True),
        _status(),
        [ProcessUsage("Server", 7, 20 * 1024 * 1024, "RSS")],
        [],
    ).text
    return (
        "> 系统启动时间：`2026-09-13 10:00:00 +08:00` · 机器人已运行：`01:02:03`" in text
        and "> Server（PID 7）：20M（RSS）" in text
    )


@func_case
async def test_ping_formatting(tester: Tester):
    """ping Markdown 引用块排版测试"""
    await tester.test(_test_simple_markdown_uses_quote_block, "简单状态使用紧凑引用块")
    await tester.test(_test_detail_markdown_uses_sections_and_process_list, "详细状态使用分区引用块")
    await tester.test(_test_detail_markdown_keeps_process_list_compact, "进程信息保持紧凑")
    return tester
