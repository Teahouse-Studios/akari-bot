"""core.queue.server 新增 WebUI 相关处理器的单元测试。"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import core.queue.server as server
from core.constants import Info
from core.tester import Tester, func_case

RAW_STATUS = {
    "browser_initialized": True,
    "debug_mode": False,
    "headless": True,
    "browser_mode": "headless",
    "keep_pages_open": False,
    "remote_only": False,
    "remote_configured": True,
    "remote_timeout": 30,
    "export_logs": True,
    "logs_path": None,
    "name": "AkariBot WebRender™",
    # 真实返回值以 BrowserContext 对象为键，任何序列化途径都无法处理。
    "contexts_open_sorted": {object(): ["https://example.test/"]},
    "contexts_total": 1,
    "leaked": False,
}


def _test_status_payload_is_serializable():
    payload = server._web_render_status_payload(RAW_STATUS)
    if payload is None:
        return False
    return (
        json.loads(json.dumps(payload)) == payload
        and payload["available"] is True
        and payload["contexts"] == [{"index": 0, "pages": ["https://example.test/"]}]
        and "contexts_open_sorted" not in payload
    )


def _test_status_payload_rejects_non_dict():
    return server._web_render_status_payload(None) is None


async def _test_runtime_stats_reports_backend_and_counters():
    with (
        patch.object(server.JobQueueServer, "backend", SimpleNamespace(name="websocket")),
        patch.object(server.Info, "command_parsed", 5),
        patch.object(server.Info, "message_parsed", 7),
    ):
        result = await server.get_runtime_stats()
    return result == {"jobqueue_backend": "websocket", "command_parsed": 5, "message_parsed": 7}


async def _test_process_usage_reports_failures_as_data():
    with patch.object(server, "gather_process_usage", new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await server.get_process_usage()
    return result == {"items": [], "failures": [], "error": "RuntimeError"}


async def _test_control_web_render_rejects_unknown_action():
    with patch.object(server, "init_web_render", new=AsyncMock()) as init:
        result = await server.control_web_render("bogus")
    return result["ok"] is False and result["error"] == "invalid_action" and init.await_count == 0


async def _test_control_web_render_updates_info_status():
    previous = Info.web_render_status
    try:
        with (
            patch.object(server, "init_web_render", new=AsyncMock(return_value=True)),
            patch.object(server, "check_web_render_status", new=AsyncMock(return_value=True)),
            patch.object(server, "_web_render_status_detail", new=AsyncMock(return_value={"available": True})),
        ):
            result = await server.control_web_render("start")
            updated = Info.web_render_status
        return result["ok"] is True and updated is True
    finally:
        Info.web_render_status = previous


async def _test_test_web_render_validates_before_rendering():
    with patch.object(server, "enable_web_render", False):
        disabled = await server.test_web_render({"mode": "screenshot", "url": "https://example.test/"})
    with (
        patch.object(server, "enable_web_render", True),
        patch.object(server, "_web_render_status_detail", new=AsyncMock(return_value={"available": True})),
        patch.object(server.web_render, "page_screenshot", new=AsyncMock()) as screenshot,
        patch.object(server.web_render, "source", new=AsyncMock()) as source,
    ):
        invalid_mode = await server.test_web_render({"mode": "video"})
        missing_source = await server.test_web_render({"mode": "source"})
        missing_screenshot = await server.test_web_render({"mode": "screenshot"})
    return (
        disabled["ok"] is False
        and disabled["error"] == "web_render_disabled"
        and invalid_mode["error"] == "invalid_mode"
        and missing_source["error"] == "missing_target"
        and missing_screenshot["error"] == "missing_target"
        # 被拦下的请求不得触达依赖库
        and screenshot.await_count == 0
        and source.await_count == 0
    )


async def _test_test_web_render_returns_base64_images():
    with (
        patch.object(server, "enable_web_render", True),
        patch.object(server, "_web_render_status_detail", new=AsyncMock(return_value={"available": True})),
        patch.object(
            server.web_render,
            "page_screenshot",
            new=AsyncMock(return_value=["QUJD", None, 123]),
        ) as screenshot,
    ):
        result = await server.test_web_render({"mode": "screenshot", "url": "https://example.test/", "width": 320})
    return (
        result["ok"] is True
        and result["images"] == ["QUJD"]
        and result["output_type"] == "jpeg"
        and result["error"] is None
        and screenshot.await_args.args[0].width == 320
    )


async def _test_test_web_render_truncates_source():
    long_source = "x" * (server.WEB_RENDER_TEST_MAX_SOURCE_CHARS + 1)
    with (
        patch.object(server, "enable_web_render", True),
        patch.object(server, "_web_render_status_detail", new=AsyncMock(return_value={"available": True})),
        patch.object(server.web_render, "source", new=AsyncMock(return_value=long_source)),
    ):
        result = await server.test_web_render({"mode": "source", "url": "https://example.test/"})
    return (
        result["ok"] is True
        and result["source_truncated"] is True
        and len(result["source"]) == server.WEB_RENDER_TEST_MAX_SOURCE_CHARS
        and result["images"] == []
    )


@func_case
async def test_webrender_rpc(tester: Tester):
    """core.queue.server: 状态净化与渲染测试参数校验测试"""
    await tester.test(_test_status_payload_is_serializable, "WebRender 状态净化测试")
    await tester.test(_test_status_payload_rejects_non_dict, "WebRender 状态非法输入测试")
    await tester.test(_test_runtime_stats_reports_backend_and_counters, "运行时统计测试")
    await tester.test(_test_process_usage_reports_failures_as_data, "进程占用失败回报测试")
    await tester.test(_test_control_web_render_rejects_unknown_action, "WebRender 控制非法 action 测试")
    await tester.test(_test_control_web_render_updates_info_status, "WebRender 控制状态回写测试")
    await tester.test(_test_test_web_render_validates_before_rendering, "渲染测试参数校验测试")
    await tester.test(_test_test_web_render_returns_base64_images, "渲染测试截图净化测试")
    await tester.test(_test_test_web_render_truncates_source, "渲染测试源码截断测试")

    return tester
