import colorsys
import os
import re
from typing import Tuple, Union

import numpy as np
import ujson as json
import webcolors
from PIL import Image, ImageDraw, ImageFont

from core.builtins import Bot, Image as BotImage
from core.component import module

c = module('color', alias='colour', developers=['Dianliang233'], desc='{color.help.desc}')

font = ImageFont.truetype('assets/SourceHanSansCN-Normal.ttf', 40)

with open(os.path.dirname(os.path.abspath(__file__)) + '/material_colors.json', 'r', encoding='utf-8') as f:
    material_colors = material_colors_names_to_hex = json.load(f)
    material_colors_hex_to_names = {v: k for k, v in material_colors.items()}

# https://github.com/ubernostrum/webcolors/issues/18
css_names_to_hex = {**webcolors.CSS3_NAMES_TO_HEX, 'rebeccapurple': '#663399'}
css_hex_to_names = {**webcolors.CSS3_HEX_TO_NAMES, '#663399': 'rebeccapurple'}


@c.command('[<color>] {{color.help}}')
@c.command()
async def _(msg: Bot.MessageSession, color: str = None):
    if not color:
        color = webcolors.HTML5SimpleColor(*(np.random.randint(0, 256, 3)))
    elif css_names_to_hex.get(color):
        color = webcolors.html5_parse_simple_color(css_names_to_hex[color])
    elif material_colors_names_to_hex.get(color):
        color = webcolors.html5_parse_simple_color(material_colors_names_to_hex[color])
    elif re.match(r'^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', color):
        # add hash if missing
        if color[0] != '#':
            color = '#' + color
        if len(color) == 4:
            color = '#' + color[1] * 2 + color[2] * 2 + color[3] * 2
        color = webcolors.html5_parse_simple_color(color)
    elif re.match(r'^rgb\(\d{1,3},\s?\d{1,3},\s?\d{1,3}\)$', color):
        color = color[4:-1].split(',')
        color = webcolors.HTML5SimpleColor(*(int(x.strip()) for x in color))
    elif re.match(r'^rgb\(\d{1,3}%,\s?\d{1,3}%,\s?\d{1,3}%\)$', color):
        color = color[4:-1].split(',')
        color = webcolors.HTML5SimpleColor(*(int(x.strip()[:-1]) * 255 / 100 for x in color))
    elif re.match(r'^hsl\(\d{1,3},\s?\d{1,3}%,\s?\d{1,3}%\)$', color):
        color = color[4:-1].split(',')
        color = colorsys.hls_to_rgb(int(color[0].strip()) / 360,
                                    int(color[2].strip()[:-1]) / 100,
                                    int(color[1].strip()[:-1]) / 100)
        color = webcolors.HTML5SimpleColor(*(int(x * 255) for x in color))
    elif re.match(r'^hsl\(\d{1,3}deg,\s?\d{1,3}%,\s?\d{1,3}%\)$', color):
        color = color[4:-1].split(',')
        color = colorsys.hls_to_rgb(int(color[0].strip()[:-3]) / 360,
                                    int(color[2].strip()[:-1]) / 100,
                                    int(color[1].strip()[:-1]) / 100)
        color = webcolors.HTML5SimpleColor(*(int(x * 255) for x in color))
    else:
        await msg.finish(msg.locale.t('color.message.invalid'))

    color_hex = '#%02x%02x%02x' % color
    color_rgb = 'rgb(%d, %d, %d)' % color
    color_hsl = colorsys.rgb_to_hls(color[0] / 255, color[1] / 255, color[2] / 255)
    color_hsl = 'hsl(%d, %d%%, %d%%)' % (color_hsl[0] * 360, color_hsl[2] * 100, color_hsl[1] * 100)
    luminance = get_luminance(color)

    contrast = (0, 0, 0) if luminance > 140 else (255, 255, 255)

    img = Image.new('RGB', (500, 500), color=color)
    draw = ImageDraw.Draw(img)

    css_color_name_raw = get_color_name(color, css_hex_to_names)
    css_color_name = ''
    css_color_name_short = ''
    if css_color_name_raw[1]:
        css_color_name = f'\n{msg.locale.t("color.message.css")}{css_color_name_raw[0]}'
        if css_color_name_raw[0] != 'black' and css_color_name_raw[0] != 'white':
            css_color_name_short = f'{css_color_name_raw[0]}\n'
    elif css_color_name_raw[0]:
        css_color_name = f'\n{msg.locale.t("color.message.css.approximate")}{css_color_name_raw[0]}'

    material_color_name_raw = get_color_name(color, material_colors_hex_to_names)
    material_color_name = ''
    material_color_name_short = ''
    if material_color_name_raw[1]:
        material_color_name = f'\n{msg.locale.t("color.message.md")}{material_color_name_raw[0]}'
        material_color_name_short = f'{material_color_name_raw[0]}\n'
    elif material_color_name_raw[0]:
        material_color_name = f'\n{msg.locale.t("color.message.md.approximate")}{material_color_name_raw[0]}'

    draw.multiline_text(
        (250,
         250),
        f'{css_color_name_short}{material_color_name_short}{color_hex}\n{color_rgb}\n{color_hsl}',
        font=font,
        fill=contrast,
        anchor='mm',
        align='center',
        spacing=20)
    await msg.finish(
        [f'HEX：{color_hex}\nRGB：{color_rgb}\nHSL：{color_hsl}{css_color_name}{material_color_name}', BotImage(img)])


def get_luminance(color: webcolors.HTML5SimpleColor):
    return color.red * 0.2126 + color.green * 0.7152 + color.blue * 0.0722


def get_color_name(color: webcolors.HTML5SimpleColor, name_dict) -> Tuple[Union[str, None], bool]:
    # check exact match
    hex_name = webcolors.rgb_to_hex(color)
    if hex_name in name_dict:
        return name_dict[hex_name], True
    color_name = None
    min_dist = 1000000
    for name, value in name_dict.items():
        dist = np.linalg.norm(np.array(color) - np.array(webcolors.html5_parse_simple_color(name)))
        if dist < min_dist:
            min_dist = dist
            color_name = value
    return color_name, False
