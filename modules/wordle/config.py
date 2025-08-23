from . import wordle

@wordle.config()
class WordleConfig:
    """
    Wordle module configuration items.
    """
    wordle_disable_image: bool = False