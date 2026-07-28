from core.config.decorator import on_module_config


@on_module_config("maimai", secret=True)
class MaimaiSecretConfig:
    diving_fish_developer_token: str = ""
    lxns_developer_token: str = ""
