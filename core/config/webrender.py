"""WebRender 配置模板。"""

from core.config.decorator import on_config


@on_config("webrender")
class WebRenderConfig:
    enable: bool = False
    browser_type: str = "chrome"
    browser_executable_path: str = ""
    remote_only: bool = False
    remote_web_render_url: str = ""
    headless: bool = True
