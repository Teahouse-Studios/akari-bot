import traceback

from akari_bot_webrender.functions.main import WebRender
from akari_bot_webrender.functions.options import ElementScreenshotOptions, PageScreenshotOptions, SourceOptions, \
    SectionScreenshotOptions, LegacyScreenshotOptions

from core.config import Config

enable_web_render = Config("enable_webrender", False)
remote_web_render_url = Config("remote_web_render_url", "", get_url=True)
web_render_browser = Config("web_render_browser", "chrome", False)

web_render = WebRender(debug=False, remote_webrender_url=remote_web_render_url)


async def init_web_render():
    if enable_web_render:
        try:
            await web_render.browser_init(browse_type=web_render_browser)
            return True
        except Exception as e:
            print(f"WebRender initialization failed: {e}")
            traceback.print_exc()
    else:
        print("WebRender is disabled in the configuration.")
    return False


async def close_web_render():
    if enable_web_render:
        await web_render.browser_close()


__all__ = [
    "web_render",
    "init_web_render",
    "close_web_render",
    ElementScreenshotOptions,
    PageScreenshotOptions,
    SourceOptions,
    SectionScreenshotOptions,
    LegacyScreenshotOptions]
