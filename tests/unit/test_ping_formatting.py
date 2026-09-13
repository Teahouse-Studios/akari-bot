"""ping 在 Markdown 与 Markdown 扩展平台上的排版测试。"""

from types import SimpleNamespace

from core.i18n import Locale
from core.queue.diagnostics import ProcessUnavailable, ProcessUsage
from core.tester import func_case, Tester
from modules.core.utils import _PingStatus, _build_ping_detail_markdown, _build_ping_simple_markdown


def _msg(*, markdown: bool, extension: bool):
    return SimpleNamespace(
        session_info=SimpleNamespace(
            locale=Locale("zh_cn"),
            support_markdown=markdown,
            support_markdown_extension=extension,
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


def _test_simple_markdown_uses_bullet_list():
    text = _build_ping_simple_markdown(
        _msg(markdown=True, extension=False),
        bot_running_time="01:02:03",
        cpu_percent=12.5,
        ram_percent=50.0,
        disk_percent=20.0,
    ).text
    return text.startswith("**Pong!**") and "- **机器人已运行：** `01:02:03`" in text and "| 项目 | 状态 |" not in text


def _test_simple_markdown_extension_uses_table():
    text = _build_ping_simple_markdown(
        _msg(markdown=True, extension=True),
        bot_running_time="01:02:03",
        cpu_percent=12.5,
        ram_percent=50.0,
        disk_percent=20.0,
    ).text
    return (
        "| 项目 | 状态 |" in text
        and "| --- | --- |" in text
        and "| 机器人已运行 | `01:02:03` |" in text
        and "| 磁盘容量 | `20.0%` |" in text
    )


def _test_detail_markdown_uses_sections_and_process_table():
    text = _build_ping_detail_markdown(
        _msg(markdown=True, extension=True),
        _status(),
        [ProcessUsage("QQ", 42, 10 * 1024 * 1024, "USS")],
        [ProcessUnavailable("Discord", "timeout")],
    ).text
    return (
        "**系统**" in text
        and "**资源**" in text
        and "**各进程内存占用**" in text
        and "AMD \\| Ryzen" in text
        and "| QQ | 42 | `10M（USS）` |" in text
        and "| Discord | - | `不可用（timeout）` |" in text
    )


def _test_detail_markdown_uses_process_list_without_extension():
    text = _build_ping_detail_markdown(
        _msg(markdown=True, extension=False),
        _status(),
        [ProcessUsage("Server", 7, 20 * 1024 * 1024, "RSS")],
        [],
    ).text
    return "- **系统启动时间：**" in text and "AMD | Ryzen" in text and "- Server（PID 7）：20M（RSS）" in text


@func_case
async def test_ping_formatting(tester: Tester):
    """ping Markdown 排版与平台能力分级测试"""
    await tester.test(_test_simple_markdown_uses_bullet_list, "普通 Markdown 使用列表")
    await tester.test(_test_simple_markdown_extension_uses_table, "Markdown 扩展使用表格")
    await tester.test(_test_detail_markdown_uses_sections_and_process_table, "详细状态使用分区与进程表")
    await tester.test(_test_detail_markdown_uses_process_list_without_extension, "无扩展时进程使用列表")
    return tester
