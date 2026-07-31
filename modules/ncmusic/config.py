from core.config.decorator import on_module_config


@on_module_config("ncmusic")
class NcmusicConfig:
    ncmusic_enable_card: bool = False


@on_module_config("ncmusic", secret=True)
class NcmusicSecretConfig:
    ncmusic_api: str = ""
