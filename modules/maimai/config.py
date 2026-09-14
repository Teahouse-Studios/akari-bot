from core.config.decorator import on_module_config


@on_module_config("maimai")
class MaimaiConfig:
    diving_fish_client_id: str = ""
    lxns_client_id: str = ""


@on_module_config("maimai", secret=True)
class MaimaiSecretConfig:
    diving_fish_client_secret: str = ""
    lxns_developer_token: str = ""
    lxns_client_secret: str = ""
