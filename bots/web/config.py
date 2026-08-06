from core.config.decorator import on_bot_config


@on_bot_config("web")
class WebConfig:
    enable: bool = True
    enable_https: bool = False
    web_host: str = "127.0.0.1"
    web_port: int = 6485
    login_max_attempt: int = 5
    heartbeat_attempt: int = 3
    heartbeat_interval: int = 30
    heartbeat_timeout: int = 5


@on_bot_config("web", secret=True)
class WebSecretConfig:
    allow_origins: list = []
    forwarded_allow_ips: list = ["127.0.0.1"]
    jwt_secret: str = ""
