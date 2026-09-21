from typing import Any

from fastapi import HTTPException, Request

from bots.web.client import app, limiter, get_client_ip
from core.config import format_url
from core.config.webrender import WebRenderConfig
from core.logger import Logger
from core.queue.contracts import ServerAPI
from .auth import verify_jwt

WEB_RENDER_ACTIONS = ("start", "stop", "restart")
WEB_RENDER_MODES = ("status", "source", "screenshot")
# 服务端在渲染前会再校验一次；此处的重复校验只为让请求参数错误返回 4xx 而不是 200。
WEB_RENDER_REQUEST_ERRORS = ("invalid_options", "invalid_mode", "missing_target", "web_render_disabled")


def _local_config() -> dict[str, Any]:
    return {
        "enable": bool(WebRenderConfig.enable),
        "browser_type": WebRenderConfig.browser_type,
        "browser_executable_path": WebRenderConfig.browser_executable_path,
        "headless": bool(WebRenderConfig.headless),
        "remote_only": bool(WebRenderConfig.remote_only),
        "remote_url": format_url(WebRenderConfig.remote_web_render_url),
    }


async def _read_json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid_body")
    return body


@app.get("/api/webrender")
@limiter.limit("30/minute")
async def get_web_render(request: Request):
    verify_jwt(request)
    try:
        status = await ServerAPI.get_web_render_status_detail()
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")
    return {"config": _local_config(), "status": status}


@app.post("/api/webrender/control")
@limiter.limit("6/minute")
async def control_web_render(request: Request):
    """启动、关闭或重启服务端的 WebRender 浏览器。"""
    ip = get_client_ip(request)
    verify_jwt(request)
    body = await _read_json_body(request)
    action = body.get("action")
    if action not in WEB_RENDER_ACTIONS:
        raise HTTPException(status_code=422, detail="invalid_action")

    Logger.info(f"[WebUI] {ip} requested WebRender action: {action}")
    try:
        result = await ServerAPI.control_web_render(action)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")

    if not result.get("ok"):
        Logger.warning(f"[WebUI] {ip} failed to control WebRender ({action}): {result.get('error')}")
    return result


@app.post("/api/webrender/test")
@limiter.limit("10/minute")
async def test_web_render(request: Request):
    """执行一次渲染测试。"""
    ip = get_client_ip(request)
    verify_jwt(request)
    body = await _read_json_body(request)
    mode = body.get("mode") or "status"
    if mode not in WEB_RENDER_MODES:
        raise HTTPException(status_code=422, detail="invalid_mode")
    if mode == "source" and not body.get("url"):
        raise HTTPException(status_code=422, detail="missing_target")
    if mode == "screenshot" and not body.get("url") and not body.get("content"):
        raise HTTPException(status_code=422, detail="missing_target")

    Logger.info(f"[WebUI] {ip} started a WebRender test (mode: {mode})")
    try:
        result = await ServerAPI.test_web_render(body)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")

    if not result.get("ok"):
        error = result.get("error")
        Logger.warning(f"[WebUI] {ip} WebRender test failed ({mode}): {error}")
        if error in WEB_RENDER_REQUEST_ERRORS:
            raise HTTPException(status_code=422, detail=error)
    return result
