import orjson as json

from core.utils.web_render import webrender
from core.utils.http import download
from core.builtins import Bot, Image, Plain
from core.component import module

msw = module('msweather', desc='MSN天气查询', developers='haoye_qwq', alias='weather')


@msw.command('<city> {获取天气}')
async def _now(msg: Bot.MessageSession):
    city = msg.parsed_msg['<city>']
    url = f"https://www.msn.cn/zh-cn/weather/forecast/in-%E6%B2%B3%E5%8D%97{city}"
    weather_now = [
        Image(await download(
            webrender("element_screenshot"),
            status_code=200,
            headers={"Content-Type": "application/json"},
            method="POST",
            post_data=json.dumps({"url": url, "element": '#WeatherOverviewCurrentSection'}),
            attempt=1,
            timeout=30,
            request_private_ip=True,
        )),
        Plain(url)
    ]
    send = await msg.send_message(weather_now)
    await msg.sleep(90)
    await send.delete()
