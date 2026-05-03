from . import wordle


@wordle.config()
class WordleConfig:
    wordle_disable_image: bool = False
