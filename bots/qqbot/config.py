from core.config.decorator import on_bot_config


@on_bot_config("qqbot")
class QQBotConfig:
    enable: bool = False
    qq_bot_appid: str | int = ""
    qq_bot_openid: str = ""
    qq_bot_enable_send_url: bool = False
    qq_private_bot: bool = False
    qq_typing_emoji: int = 181
    qq_limited_emoji: int = 10060
    qq_use_markdown: bool = False
    qq_navigation_sync_strict: bool = False
    qq_use_webhook: bool = False
    qq_webhook_host: str = "0.0.0.0"
    qq_webhook_port: int = 8080
    qq_webhook_path: str = "/"
    qq_bot_uid: str = ""
    qq_bot_qqnum: str = ""


@on_bot_config("qqbot", secret=True)
class QQBotSecretConfig:
    qq_bot_secret: str = ""
