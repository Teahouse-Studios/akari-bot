"""bots.web.api 单元测试 - 状态接口的运行时统计与进程内存占用。"""

import inspect
from unittest.mock import AsyncMock, patch

import bots.web.api.api as web_api
from core.queue.diagnostics import DAEMON_LABEL, ProcessUsage, usage_payload
from core.tester import Tester, func_case

PROCESSES = usage_payload([ProcessUsage(name=DAEMON_LABEL, pid=7, memory=1024, metric="RSS", threads=2)], [])
PROCESSES["error"] = None


def _patch_system_metrics():
    return (
        patch.object(web_api, "get_cpu_info", lambda: {"brand_raw": "test-cpu"}),
        patch.object(web_api.psutil, "cpu_percent", lambda interval=None: 0.0),
        patch.object(web_api.psutil, "disk_usage", lambda path: _DiskUsage()),
    )


class _DiskUsage:
    total = 2 * 1024 * 1024 * 1024
    used = 1024 * 1024 * 1024
    percent = 50.0


async def _test_server_info_reports_runtime_stats():
    endpoint = inspect.unwrap(web_api.server_info)
    stats = {"jobqueue_backend": "websocket", "command_parsed": 12, "message_parsed": 34}
    cpu_info_patch, cpu_patch, disk_patch = _patch_system_metrics()
    with (
        patch.object(web_api, "verify_jwt", lambda request: None),
        patch.object(web_api.ServerAPI, "get_bot_version", new=AsyncMock(return_value="v1")),
        patch.object(web_api.ServerAPI, "get_web_render_status", new=AsyncMock(return_value=True)),
        patch.object(web_api.ServerAPI, "get_runtime_stats", new=AsyncMock(return_value=stats)),
        patch.object(web_api.ServerAPI, "get_process_usage", new=AsyncMock(return_value=PROCESSES)),
        cpu_info_patch,
        cpu_patch,
        disk_patch,
    ):
        result = await endpoint(None)
    return (
        result["bot"]["jobqueue_backend"] == "websocket"
        and result["bot"]["command_parsed"] == 12
        and result["bot"]["message_parsed"] == 34
        and result["processes"]["items"][0]["name"] == DAEMON_LABEL
        and result["processes"]["error"] is None
    )


async def _test_server_info_degrades_without_server():
    endpoint = inspect.unwrap(web_api.server_info)
    cpu_info_patch, cpu_patch, disk_patch = _patch_system_metrics()
    with (
        patch.object(web_api, "verify_jwt", lambda request: None),
        patch.object(web_api.ServerAPI, "get_bot_version", new=AsyncMock(return_value=None)),
        patch.object(web_api.ServerAPI, "get_web_render_status", new=AsyncMock(return_value=False)),
        patch.object(web_api.ServerAPI, "get_runtime_stats", new=AsyncMock(side_effect=RuntimeError("offline"))),
        patch.object(web_api.ServerAPI, "get_process_usage", new=AsyncMock(side_effect=RuntimeError("offline"))),
        cpu_info_patch,
        cpu_patch,
        disk_patch,
    ):
        result = await endpoint(None)
    return (
        result["bot"]["jobqueue_backend"] is None
        and result["bot"]["command_parsed"] is None
        and result["processes"] == {"items": [], "failures": [], "error": "unavailable"}
        and result["os"]["system"]
    )


@func_case
async def test_webui_status(tester: Tester):
    """bots.web.api: 状态接口测试"""
    await tester.test(_test_server_info_reports_runtime_stats, "状态接口运行时统计测试")
    await tester.test(_test_server_info_degrades_without_server, "状态接口离线降级测试")

    return tester
