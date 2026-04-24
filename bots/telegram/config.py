from core.config.decorator import on_config


@on_config("telegram", "bot", False)
class AiogramConfig:
    enable: bool = False
    telegram_api_url: str = ""


@on_config("telegram", "bot", True)
class AiogramSecretConfig:
    telegram_token: str = ""
