import os

# 基本路径
assets_path = os.path.abspath("./assets")
bots_path = os.path.abspath("./bots")
cache_path = os.path.abspath("./cache")
config_path = os.path.abspath("./config")
database_path = os.path.abspath("./database")
locales_path = os.path.abspath("./core/locales")
logs_path = os.path.abspath("./logs")
modules_path = os.path.abspath("./modules")
schedulers_path = os.path.abspath("./schedulers")
webui_path = os.path.abspath("./webui")

# assets 子路径
fonts_path = os.path.join(assets_path, "fonts")
templates_path = os.path.join(assets_path, "templates")

# 字体文件路径
noto_sans_bold_path = os.path.join(fonts_path, "Noto Sans CJK Bold.otf")
noto_sans_demilight_path = os.path.join(fonts_path, "Noto Sans CJK DemiLight.otf")
noto_sans_symbol_path = os.path.join(fonts_path, "Noto Sans Symbols2 Regular.ttf")

nunito_light_path = os.path.join(fonts_path, "Nunito Light.ttf")
nunito_regular_path = os.path.join(fonts_path, "Nunito Regular.ttf")

# 特殊路径
modules_locales_path = os.path.join(modules_path, "*", "locales")
bots_info_path = os.path.join(bots_path, "*", "info.py")


class PrivateAssets:
    path = os.path.join(assets_path, "private", "default")
    os.makedirs(path, exist_ok=True)

    @classmethod
    def set(cls, path):
        path = os.path.abspath(path)
        os.makedirs(path, exist_ok=True)
        cls.path = path
