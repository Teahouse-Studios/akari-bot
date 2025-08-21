from . import mod_dl

@mod_dl.config(is_secret=True)
class ModDlConfig:
    """
    Mod Downloader module configuration items.
    """
    curseforge_api_key: str = ""
