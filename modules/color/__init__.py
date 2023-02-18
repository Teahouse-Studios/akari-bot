import re
import ujson as json
from core.builtins import Bot
from core.component import on_command
from core.logger import Logger
from core.utils.http import post_url
import colorsys

c = on_command('color', alias=['colour'], developers=['Dianliang233',], desc='提供颜色信息。')


@c.handle('<color> {提供颜色信息。}')
async def _(msg: Bot.MessageSession):
    color = msg.parsed_msg.get('<color>')
    if re.match(r'^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', color):
        color = color.lstrip('#')
        if len(color) == 3:
            color = ''.join([x * 2 for x in color])
        color = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    elif re.match(r'^rgb\(\d{1,3}, ?\d{1,3}, ?\d{1,3}\)$', color):
        color = color[4:-1].split(',')
        color = tuple(int(x) for x in color)
    elif re.match(r'^hsl\(\d{1,3}, ?\d{1,3}%, ?\d{1,3}%\)$', color):
        color = color[4:-1].split(',')
        color = [int(x[:-1]) for x in color]
        color = colorsys.hls_to_rgb(color[0] / 360, color[2] / 100, color[1] / 100)

    color_hex = '#%02x%02x%02x' % color
    color_rgb = 'rgb(%d, %d, %d)' % color
    color_hsl = colorsys.rgb_to_hls(color[0] / 255, color[1] / 255, color[2] / 255)
    color_hsl = 'hsl(%ddeg, %d%%, %d%%)' % (color_hsl[0] * 360, color_hsl[2] * 100, color_hsl[1] * 100)
    await msg.finish('HEX: %s\nRGB: %s\nHSL: %s' % (color_hex, color_rgb, color_hsl))
