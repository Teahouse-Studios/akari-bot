from core.config.decorator import on_module_config


@on_module_config("wolframalpha", secret=True)
class WolframalphaConfig:
    wolfram_alpha_appid: str = ""
