from .maimai import mai


@mai.config(secret=True)
class MaimaiSecretConfig:
    diving_fish_developer_token: str = ""
    lxns_developer_token: str = ""
