from core.config.decorator import on_config


@on_config("web", "bot", False)
class WebConfig:
    enable: bool = True
    enable_https: bool = False
    web_host: str = "127.0.0.1"
    web_port: int = 6485
    login_max_attempts: int = 5

@on_config("web", "bot", True)
class WebSecretConfig:
    allow_origins: list = []
    jwt_secret: str = ""

