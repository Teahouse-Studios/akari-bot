from core.config.decorator import on_bot_config


@on_bot_config("telegram")
class AiogramConfig:
    enable: bool = False
    telegram_api_url: str = ""


@on_bot_config("telegram", secret=True)
class AiogramSecretConfig:
    telegram_token: str = ""
