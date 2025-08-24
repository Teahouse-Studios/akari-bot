from . import w


@w.config(secret=True)
class WolframalphaConfig:
    wolfram_alpha_appid: str = ""
