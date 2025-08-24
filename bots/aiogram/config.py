from core.config.decorator import on_config


@on_config("aiogram", "bot", False)
class AiogramConfig:
    enable: bool = False
    telegram_api_url: str = ""


@on_config("aiogram", "bot", True)
class AiogramSecretConfig:
    telegram_token: str = ""
