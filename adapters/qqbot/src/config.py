from core.config.decorator import on_config


@on_config("qqbot", "bot", False)
class QQBotConfig:
    enable: bool = False
    qq_bot_appid: str | int = ""
    qq_private_bot: bool = False
    qq_bot_enable_send_url: bool = False
    qq_typing_emoji: int = 181


@on_config("qqbot", "bot", True)
class QQBotSecretConfig:
    qq_bot_secret: str = ""
