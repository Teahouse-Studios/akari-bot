from . import ncmusic


@ncmusic.config()
class NcmusicConfig:
    ncmusic_enable_card: bool = True


@ncmusic.config(secret=True)
class NcmusicSecretConfig:
    ncmusic_api: str = ""
