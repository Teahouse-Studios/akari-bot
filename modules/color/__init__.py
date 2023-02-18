import re
import colorsys

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import webcolors

from core.builtins import Bot, Image as BotImage
from core.component import on_command

c = on_command('color', alias=['colour'], developers=['Dianliang233',], desc='提供颜色信息。')

font = ImageFont.truetype('assets/SourceHanSansCN-Normal.ttf', 40)

@c.handle('<color> {提供颜色信息。}')
async def _(msg: Bot.MessageSession):
    color = msg.parsed_msg.get('<color>')
    if webcolors.CSS3_NAMES_TO_HEX.get(color) is not None:
        color = webcolors.html5_parse_simple_color(webcolors.CSS3_NAMES_TO_HEX[color])
    elif re.match(r'^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', color):
        # add hash if missing
        if color[0] != '#':
            color = '#' + color
        if len(color) == 4:
            color = '#' + color[1] * 2 + color[2] * 2 + color[3] * 2
        color = webcolors.html5_parse_simple_color(color)
    elif re.match(r'^rgb\(\d{1,3}, ?\d{1,3}, ?\d{1,3}\)$', color):
        color = color[4:-1].split(',')
        color = webcolors.HTML5SimpleColor(*(int(x) for x in color))
    elif re.match(r'^rgb\(\d{1,3}%, ?\d{1,3}%, ?\d{1,3}%\)$', color):
        color = color[4:-1].split(',')
        color = webcolors.HTML5SimpleColor(*(int(x[:-1]) * 255 / 100 for x in color))
    elif re.match(r'^hsl\(\d{1,3}, ?\d{1,3}%, ?\d{1,3}%\)$', color):
        color = color[4:-1].split(',')
        color = colorsys.hls_to_rgb(int(color[0]) / 360, int(color[2][:-1]) / 100, int(color[1][:-1]) / 100)
        color = webcolors.HTML5SimpleColor(*(int(x * 255) for x in color))
    else:
        await msg.finish('无法识别的颜色格式。')

    color_hex = '#%02x%02x%02x' % color
    color_rgb = 'rgb(%d, %d, %d)' % color
    color_hsl = colorsys.rgb_to_hls(color[0] / 255, color[1] / 255, color[2] / 255)
    color_hsl = 'hsl(%d, %d%%, %d%%)' % (color_hsl[0] * 360, color_hsl[2] * 100, color_hsl[1] * 100)
    luminance = get_luminance(color)

    contrast = (0, 0, 0) if luminance > 140 else (255, 255, 255)

    img = Image.new('RGB', (600, 600), color=color)
    draw = ImageDraw.Draw(img)

    color_name_raw = get_color_name(color)
    color_name = ''
    color_name_short = ''
    if color_name_raw[1]:
        color_name = f'\nCSS 颜色名称: {color_name_raw[0]}'
        color_name_short = f'{color_name_raw[0]}'
    elif color_name_raw[0] is not None:
        color_name = f'\n最相似的 CSS 颜色名称: {color_name_raw[0]}'

    draw.multiline_text((300, 300), f'{color_name_short}\n{color_hex}\n{color_rgb}\n{color_hsl}', font=font, fill=contrast, anchor='mm', align='center', spacing=20)
    await msg.finish([f'HEX：{color_hex}\nRGB：{color_rgb}\nHSL：{color_hsl}{color_name}', BotImage(img)])

def get_luminance(color: webcolors.HTML5SimpleColor):
    return color.red * 0.2126 + color.green * 0.7152 + color.blue * 0.0722

def get_color_name(color: webcolors.HTML5SimpleColor):
    # check exact match
    hex_name = webcolors.rgb_to_hex(color)
    if hex_name in webcolors.CSS3_HEX_TO_NAMES:
        return webcolors.CSS3_HEX_TO_NAMES[hex_name], True
    color_name = None
    min_dist = 1000000
    for name, value in webcolors.CSS3_HEX_TO_NAMES.items():
        dist = np.linalg.norm(np.array(color) - np.array(webcolors.html5_parse_simple_color(name)))
        if dist < min_dist:
            min_dist = dist
            color_name: str = value
    return color_name, False
