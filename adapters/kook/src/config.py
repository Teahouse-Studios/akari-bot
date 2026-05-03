from core.config.decorator import on_config


@on_config("kook", "bot", False)
class KookConfig:
    enable: bool = False


@on_config("kook", "bot", True)
class KookSecretConfig:
    kook_token: str = ""
