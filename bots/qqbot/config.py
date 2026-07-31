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


@on_bot_config("qqbot", secret=True)
class QQBotSecretConfig:
    qq_bot_secret: str = ""
