from core.extra.qweather import QweatherApi
from core.builtins import Bot, Plain
from core.component import module

qweather = module('qweather', desc='和风天气API查询', developers='haoye_qwq', alias={'weather':'qweather', '和风天气':'qweather', 'qweather 7d':'qweather 7days'})


@qweather.command('now <city> {获取实时天气}')
async def _now(msg: Bot.MessageSession):
    weat_now = await QweatherApi().weather_now(msg.parsed_msg['<city>'])
    weather_now = "检索到以下地区的结果：\n"
    for detail in weat_now:
        weather_now += f">>{detail['city']} 在 {detail['time']} 的天气: 气温 {detail['temp']}℃，体感温度 {detail['feelsLike']}℃；风向为 {detail['wind'][0]}，风力等级为 {detail['wind'][1]}级，风速为 {detail['wind'][2]}km/h；相对湿度为 {detail['others']['humidity']}%，过去一小时降水量为 {detail['others']['precip']}mm，大气压强为 {detail['others']['pressure']}hPa，能见度为 {detail['others']['vis']}km。\n"
    weather_now += '[90秒后撤回]'
    send = await msg.send_message(weather_now)
    await msg.sleep(90)
    await send.delete()


@qweather.command('7days <city> {获取城市的七日预报}')
async def _7days(msg: Bot.MessageSession):
    seven_days = await QweatherApi().weather_7d(msg.parsed_msg['<city>'])
    __7days__ = f"{seven_days['city']} 最近七日的天气数据: \n"
    for detail in seven_days['7days']:
        __7days__ += (detail['fxDate'] + f": 白天 {detail['textDay']}，夜晚 {detail['textNight']}；当日温度为{detail['tempMin'] + '℃~' + detail['tempMax']}℃；当日总降水量为{detail['precip']}mm\n")
    __7days__ += '[90秒后撤回]'
    send = await msg.send_message(__7days__)
    await msg.sleep(90)
    await send.delete()
