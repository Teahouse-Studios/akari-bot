from pathlib import Path

# 基本路径
assets_path = Path("./assets").resolve()
bots_path = Path("./bots").resolve()
cache_path = Path("./cache").resolve()
config_path = Path("./config").resolve()
database_path = Path("./database").resolve()
locales_path = Path("./core/locales").resolve()
logs_path = Path("./logs").resolve()
webui_path = Path("./webui").resolve()

# assets 子路径
fonts_path = assets_path / "fonts"
templates_path = assets_path / "templates"

# 字体文件路径
noto_sans_bold_path = fonts_path / "Noto Sans CJK Bold.otf"
noto_sans_demilight_path = fonts_path / "Noto Sans CJK DemiLight.otf"
noto_sans_symbol_path = fonts_path / "Noto Sans Symbols2 Regular.ttf"

# 特殊路径
modules_locales_path = str(Path("./modules").resolve() / "*" / "locales")
bots_info_path = str(bots_path / "*" / "info.py")


class PrivateAssets:
    path = assets_path / "private" / "default"
    path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def set(cls, path: str | Path):
        path_ = Path(path).resolve()
        path_.mkdir(parents=True, exist_ok=True)
        cls.path = path_
