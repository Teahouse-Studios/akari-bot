from .maimai import mai

@mai.config(is_secret=True)
class MaimaiSecretConfig:
    """
    Maimai module configuration items.
    """
    diving_fish_developer_token: str = ""
