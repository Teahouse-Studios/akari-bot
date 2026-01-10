from pathlib import Path

from akari_bot_webrender.functions.main import WebRender
from akari_bot_webrender.functions.options import ElementScreenshotOptions, PageScreenshotOptions, SourceOptions, \
    SectionScreenshotOptions, LegacyScreenshotOptions

from core.config import Config
from core.constants.path import logs_path
from core.logger import Logger


enable_web_render = Config("enable_web_render", False, table_name="webrender")
remote_web_render_url = Config("remote_web_render_url", cfg_type=str, table_name="webrender", get_url=True)
web_render_browser = Config("browser_type", "chrome", table_name="webrender")
browser_executable_path = Config("browser_executable_path", cfg_type=str, table_name="webrender")
remote_only = Config("remote_only", False, table_name="webrender")

web_render = WebRender(debug=False,
                       remote_webrender_url=remote_web_render_url,
                       remote_only=remote_only,
                       export_logs=True,
                       logs_path=str(logs_path))


async def init_web_render():
    if enable_web_render:
        return await web_render.browser_init(browse_type=web_render_browser, executable_path=Path(browser_executable_path) if browser_executable_path else None)
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
    "LegacyScreenshotOptions"]
