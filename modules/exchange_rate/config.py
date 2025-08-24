from . import excr


@excr.config(secret=True)
class ExchangeRateConfig:
    exchange_rate_api_key: str = ""
