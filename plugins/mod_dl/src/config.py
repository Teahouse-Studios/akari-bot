from . import mod_dl


@mod_dl.config(secret=True)
class ModDlConfig:
    curseforge_api_key: str = ""
