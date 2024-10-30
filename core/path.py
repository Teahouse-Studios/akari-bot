from os.path import abspath, join

# 基本路径
assets_path = abspath('./assets')
bots_path = abspath('./bots')
cache_path = abspath('./cache')
config_path = abspath('./config')
locales_path = abspath('./locales')
logs_path = abspath('./logs')
modules_path = abspath('./modules')
schedulars_path = abspath('./schedulers')

# assets 子路径
fonts_path = join(assets_path, 'fonts')
templates_path = join(assets_path, 'templates')

# 字体文件路径
noto_sans_bold_path = join(fonts_path, 'Noto Sans CJK Bold.otf')
noto_sans_demilight_path = join(fonts_path, 'Noto Sans CJK DemiLight.otf')
noto_sans_symbol_path = join(fonts_path, 'Noto Sans Symbols2 Regular.ttf')

nunito_light_path = join(fonts_path, 'Nunito Light.ttf')
nunito_regular_path = join(fonts_path, 'Nunito Regular.ttf')

# 特殊路径
modules_locales_path = join(modules_path, '*', 'locales')
bots_info_path = join(bots_path, '*', 'info.py')
