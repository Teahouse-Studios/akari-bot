from io import BytesIO
from PIL import Image as PILImage

import orjson as json
import base64

from core.utils.web_render import webrender
from core.utils.http import download
from core.builtins import Bot, Image, Plain
from core.component import module
from urllib.parse import quote

msw = module('msweather', desc='MSN天气查询', developers='haoye_qwq', alias='weather')


@msw.command('<city> {获取天气}')
async def _now(msg: Bot.MessageSession):
    city = msg.parsed_msg['<city>']
    url = f"www.msn.cn/zh-cn/weather/forecast/in-{city}"
    url = 'https://' + quote(url)
    img = await download(
            webrender("page/"),
            status_code=200,
            headers={"Content-Type": "application/json"},
            method="POST",
            post_data=json.dumps({"url": url}),
            attempt=1,
            timeout=30,
            request_private_ip=True,
        )
    with open(img) as read:
        load_img = json.loads(read.read())
    weather_now = []
    for x in load_img:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        weather_now.append(Image(bimg))
    weather_now.append(Plain(url))
    await msg.finish(weather_now)

# @msw.command('month <city> {获取周天气}')
# async def _month(msg:Bot.MessageSession):
#     city = msg.parsed_msg['<city>']
#     url = f"www.msn.cn/zh-cn/weather/forecast/in-{city}"
#     url = 'https://'+quote(url)
#     weather_now = [
#         Image(await download(
#             webrender("section_screenshot"),
#             status_code=200,
#             headers={"Content-Type": "application/json"},
#             method="POST",
#             post_data=json.dumps({"url": url, "section": ['#WeatherOverviewCurrentSection']}),
#             attempt=1,
#             timeout=30,
#             request_private_ip=True,
#         )),
#         Plain(url)
#     ]
#     await msg.finish(weather_now)
