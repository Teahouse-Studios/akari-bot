from core.config.decorator import on_config


@on_config("webrender")
class WebRenderConfig:
    enable_web_render: bool = False
    remote_web_render_url: str = ""
    browser_type: str = "chrome"
    browser_executable_path: str = ""
