from core.config.decorator import on_module_config


@on_module_config("coin")
class CoinConfig:
    coin_limit: int = 10000
    coin_faceup_weight: int = 4997
    coin_facedown_weight: int = 4997
    coin_stand_weight: int = 6
