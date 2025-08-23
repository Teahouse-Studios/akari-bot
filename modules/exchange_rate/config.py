from . import excr

@excr.config(is_secret=True)

class ExchangeRateConfig:
    """
    Exchange Rate module configuration items.
    """

    exchange_rate_api_key: str = ""