from core.config.decorator import on_config

@on_config("aiogram", "bot", False)
class AiogramConfig:
    """
    Aiogram bot configuration.
    """

    enable: bool = False
    telegram_api_url: str = ""


@on_config("aiogram", "bot", True)
class AiogramSecretConfig:
    """
    Aiogram bot secret configuration.
    """

    telegram_token: str = ""
