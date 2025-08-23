from . import osu

@osu.config(is_secret=True)
class OsuConfig:
    """
    Osu! module configuration items.
    """

    osu_api_key: str = ""
