from core.config.decorator import on_bot_config


@on_bot_config("kook")
class KookConfig:
    enable: bool = False


@on_bot_config("kook", secret=True)
class KookSecretConfig:
    kook_token: str = ""
