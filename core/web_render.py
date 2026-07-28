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
)


async def init_web_render():
    if enable_web_render:
        return await web_render.browser_init(
            browser_type=web_render_browser,
            executable_path=Path(browser_executable_path) if browser_executable_path else None,
        )
    Logger.info("WebRender is disabled in the configuration.")
    return False


async def close_web_render():
    if enable_web_render:
        await web_render.browser_close()


__all__ = [
    "web_render",
    "init_web_render",
    "close_web_render",
    "ElementScreenshotOptions",
    "PageScreenshotOptions",
    "SourceOptions",
    "SectionScreenshotOptions",
    "LegacyScreenshotOptions",
    "RawOptions",
]
