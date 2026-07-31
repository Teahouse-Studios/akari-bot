from core.config.decorator import on_module_config


@on_module_config("wordle")
class WordleConfig:
    wordle_disable_image: bool = False
