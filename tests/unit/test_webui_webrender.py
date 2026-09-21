"""bots.web.api.webrender 单元测试 - 参数校验与 RPC 转发。"""

import inspect
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

import bots.web.api.webrender as webrender_api
from core.tester import Tester, func_case

STATUS = {
    "available": True,
    "browser_initialized": True,
    "browser_mode": "headless",
    "headless": True,
    "remote_only": False,
    "remote_configured": False,
    "contexts": [],
    "contexts_total": 0,
    "leaked": False,
}


class FakeRequest:
    def __init__(self, body=None):
        self._body = body

    async def json(self):
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


async def _call(call) -> tuple[int, object]:
    try:
        result = await call()
    except HTTPException as exc:
        return exc.status_code, exc.detail
    return getattr(result, "status_code", 200), result


@contextmanager
def _patched(**rpc_results):
    with ExitStack() as stack:
        stack.enter_context(patch.object(webrender_api, "verify_jwt", lambda request: None))
        stack.enter_context(patch.object(webrender_api, "get_client_ip", lambda request: "test"))
        for name, kwargs in rpc_results.items():
            stack.enter_context(patch.object(webrender_api.ServerAPI, name, new=AsyncMock(**kwargs)))
        yield


async def _test_webrender_status_merges_config_with_rpc():
    endpoint = inspect.unwrap(webrender_api.get_web_render)
    with _patched(get_web_render_status_detail={"return_value": STATUS}):
        return await endpoint(None) == {"config": webrender_api._local_config(), "status": STATUS}


async def _test_webrender_status_survives_missing_server():
    endpoint = inspect.unwrap(webrender_api.get_web_render)
    with _patched(get_web_render_status_detail={"side_effect": RuntimeError("offline")}):
        return await _call(lambda: endpoint(None)) == (400, "Bad request")


async def _test_webrender_control_validates_action():
    endpoint = inspect.unwrap(webrender_api.control_web_render)
    control_result = {"ok": True, "error": None, "status": STATUS}
    with _patched(control_web_render={"return_value": control_result}):
        invalid = await _call(lambda: endpoint(FakeRequest({"action": "kill"})))
        not_object = await _call(lambda: endpoint(FakeRequest(["start"])))
        no_body = await _call(lambda: endpoint(FakeRequest()))
        accepted = await _call(lambda: endpoint(FakeRequest({"action": "restart"})))
    return (
        invalid == (422, "invalid_action")
        and not_object == (400, "invalid_body")
        and no_body == (400, "invalid_json")
        and accepted == (200, control_result)
    )


async def _test_webrender_control_reports_runtime_failure():
    endpoint = inspect.unwrap(webrender_api.control_web_render)
    failure = {"ok": False, "error": "control_failed", "status": None}
    with _patched(control_web_render={"return_value": failure}):
        return await _call(lambda: endpoint(FakeRequest({"action": "start"}))) == (200, failure)


async def _test_webrender_test_validates_target():
    endpoint = inspect.unwrap(webrender_api.test_web_render)
    disabled = {"ok": False, "mode": "screenshot", "error": "web_render_disabled"}
    with _patched(test_web_render={"return_value": disabled}):
        bad_mode = await _call(lambda: endpoint(FakeRequest({"mode": "video"})))
        empty_source = await _call(lambda: endpoint(FakeRequest({"mode": "source"})))
        empty_screenshot = await _call(lambda: endpoint(FakeRequest({"mode": "screenshot"})))
        disabled_result = await _call(
            lambda: endpoint(FakeRequest({"mode": "screenshot", "url": "https://example.test/"}))
        )
    return (
        bad_mode == (422, "invalid_mode")
        and empty_source == (422, "missing_target")
        and empty_screenshot == (422, "missing_target")
        # 服务端明确回报未启用时，接口同样以 422 呈现原因码
        and disabled_result == (422, "web_render_disabled")
    )


async def _test_webrender_test_forwards_render_result():
    endpoint = inspect.unwrap(webrender_api.test_web_render)
    success = {
        "ok": True,
        "mode": "screenshot",
        "elapsed": 1.5,
        "status": STATUS,
        "source": None,
        "source_truncated": False,
        "images": ["AAAA"],
        "output_type": "jpeg",
        "error": None,
    }
    rendered_failure = {**success, "ok": False, "images": [], "error": "render_failed"}
    request = FakeRequest({"mode": "screenshot", "url": "https://example.test/"})
    with _patched(test_web_render={"return_value": success}):
        ok = await _call(lambda: endpoint(request))
    with _patched(test_web_render={"return_value": rendered_failure}):
        failed = await _call(lambda: endpoint(request))
    return ok == (200, success) and failed == (200, rendered_failure)


@func_case
async def test_webui_webrender(tester: Tester):
    """bots.web.api.webrender: WebRender 接口测试"""
    await tester.test(_test_webrender_status_merges_config_with_rpc, "WebRender 状态合并测试")
    await tester.test(_test_webrender_status_survives_missing_server, "WebRender 状态降级测试")
    await tester.test(_test_webrender_control_validates_action, "WebRender 控制参数校验测试")
    await tester.test(_test_webrender_control_reports_runtime_failure, "WebRender 控制失败回报测试")
    await tester.test(_test_webrender_test_validates_target, "WebRender 测试参数校验测试")
    await tester.test(_test_webrender_test_forwards_render_result, "WebRender 测试结果转发测试")

    return tester
