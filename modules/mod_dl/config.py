from core.config.decorator import on_module_config


@on_module_config("mod_dl", secret=True)
class ModDlConfig:
    curseforge_api_key: str = ""
