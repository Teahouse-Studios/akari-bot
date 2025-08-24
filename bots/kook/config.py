from core.config.decorator import on_config


@on_config("kook", "bot", False)
class KookConfig:
    """
    Kook bot configuration.
    """
    enable: bool = False


@on_config("kook", "bot", True)
class KookSecretConfig:
    """
    Kook bot secret configuration.
    """
    kook_token: str = ""
