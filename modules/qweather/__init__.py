from core.extra.qweather import QweatherApi
from core.builtins import Bot, Plain
from core.component import module

qweather = module('qweather', desc='和风天气API查询', developers='haoye_qwq', alias=['weather','天气','和风天气'])

@qweather.command('now <location|city> {获取实时天气}')
async def _now(msg: Bot.MessageSession):
    weat_now = await QweatherApi().weather_now(msg.parsed_msg['<location|city>'])
    weather_now = [Plain("检索到以下地区的结果：\n")]
    for detail in weat_now:
        weather_now.append(f">>{detail['city']} 在 {detail['time']} 的天气: 气温 {detail['temp']}℃，体感温度 {detail['feelsLike']}℃；风向为 {detail['wind'][0]}，风力等级为 {detail['wind'][1]}级，风速为 {detail['wind'][2]}km/h；相对湿度为 {detail['others']['humidity']}%，过去一小时降水量为 {detail['others']['precip']}mm，大气压强为 {detail['others']['pressure']}hPa，能见度为 {detail['others']['vis']}km。\n")
