from . import ncmusic

@ncmusic.config()
class NcmusicConfig:
    """
    NetEase Cloud Music module configuration items.
    """
    ncmusic_enable_card: bool = True

@ncmusic.config(is_secret=True)
class NcmusicSecretConfig:
    """
    NetEase Cloud Music module secret configuration items.
    """
    ncmusic_api: str = ""
