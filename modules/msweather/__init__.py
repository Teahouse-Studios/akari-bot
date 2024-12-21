import orjson as json

from core.utils.web_render import webrender
from core.utils.http import download
from core.builtins import Bot, Image, Plain
from core.component import module
from urllib.parse import quote

from modules.wiki.utils.screenshot_image import generate_screenshot_v2

msw = module('msweather', desc='MSN天气查询', developers='haoye_qwq', alias='weather')


@msw.command('<city> {获取天气}')
async def _now(msg: Bot.MessageSession):
    city = msg.parsed_msg['<city>']
    url = f"www.msn.cn/zh-cn/weather/forecast/in-{city}"
    url = 'https://' + quote(url)
    img = await generate_screenshot_v2(url, element=[
        'div#WeatherOverviewCurrentSection.weatherOverview_root-DS-EntryPoint1-1'], content_mode=False)
    msg_ = []
    if img:
        for i in img:
            msg_.append(Image(i))
    msg_.append(Plain(url))
    await msg.finish(msg_)


@msw.command('month <city> {获取周天气}')
async def _month(msg: Bot.MessageSession):
    city = msg.parsed_msg['<city>']
    url = f"www.msn.cn/zh-cn/weather/forecast/in-{city}"
    url = 'https://' + quote(url)
    img = await generate_screenshot_v2(url, element=[
        'div.monthCalendarRoot-DS-EntryPoint1-1.visualReady'], content_mode=False)
    msg_ = []
    if img:
        for i in img:
            msg_.append(Image(i))
    msg_.append(Plain(url))
    await msg.finish(msg_)
