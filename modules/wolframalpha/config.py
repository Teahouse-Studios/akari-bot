from . import w

@w.config(is_secret=True)

class WolframalphaConfig:
    """
    WolframAlpha module configuration items.
    """

    wolfram_alpha_appid: str = ""
