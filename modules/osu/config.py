from . import osu


@osu.config(secret=True)
class OsuConfig:
    osu_api_key: str = ""
