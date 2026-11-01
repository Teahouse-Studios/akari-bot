from core.config.decorator import on_bot_config


@on_bot_config("satori")
class SatoriConfig:
    enable: bool = False
    satori_host: str = "127.0.0.1"
    satori_port: int = 5140
    satori_path: str = ""
    satori_secure: bool = False
    satori_timeout: int = 30
    satori_enable_listening_self_message: bool = False
    satori_admin_roles: list = ["admin", "owner"]
    satori_typing_emoji: str = "⌛"
    satori_limited_emoji: str = "❌"


@on_bot_config("satori", secret=True)
class SatoriSecretConfig:
    satori_token: str = ""
