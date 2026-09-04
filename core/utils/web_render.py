from pathlib import Path

from akari_bot_webrender.functions.main import WebRender
from akari_bot_webrender.functions.options import (
    ElementScreenshotOptions,
    PageScreenshotOptions,
    SourceOptions,
    SectionScreenshotOptions,
    LegacyScreenshotOptions,
    RawOptions,
)

from core.config import format_url
from core.config.base import WebRenderConfig
from core.constants.path import logs_path
from core.logger import Logger

enable_web_render = WebRenderConfig.enable
remote_web_render_url = format_url(WebRenderConfig.remote_web_render_url)
web_render_browser = WebRenderConfig.browser_type
browser_executable_path = WebRenderConfig.browser_executable_path
remote_only = WebRenderConfig.remote_only

web_render = WebRender(
    debug=False,
    remote_webrender_url=remote_web_render_url,
    remote_only=remote_only,
    export_logs=True,
    logs_path=str(logs_path),
    headless=WebRenderConfig.headless,
)


async def init_web_render():
    if not enable_web_render:
        Logger.info("WebRender is disabled in the configuration.")
        return False

    # remote_only 的所有操作（包括 status）均由依赖库转发至远端；此时启动本地
    # Playwright 不仅违背配置，还会让无浏览器环境中的可用远端服务被误判为不可用。
    if remote_only:
        return await check_web_render_status()

    initialized = await web_render.browser_init(
        browser_type=web_render_browser,
        executable_path=Path(browser_executable_path) if browser_executable_path else None,
    )
    return bool(initialized) and await check_web_render_status()


async def check_web_render_status() -> bool:
    """检查当前配置所选 WebRender 后端是否可用。"""
    if not enable_web_render:
        return False
    status = await web_render.status()
    return isinstance(status, dict) and bool(status.get("browser_initialized"))


async def close_web_render():
    if not enable_web_render:
        return False
    if remote_only:
        Logger.info("Remote-only WebRender does not own a local browser to close.")
        return True
    return await web_render.browser_close()


__all__ = [
    "web_render",
    "init_web_render",
    "check_web_render_status",
    "close_web_render",
    "ElementScreenshotOptions",
    "PageScreenshotOptions",
    "SourceOptions",
    "SectionScreenshotOptions",
    "LegacyScreenshotOptions",
    "RawOptions",
]
