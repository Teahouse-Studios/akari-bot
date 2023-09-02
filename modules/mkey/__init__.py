from core.component import module
from core.builtins import Bot
from .generator import get_mkey

mk = module('mkey', desc='计算任天堂系列主机的家长控制重置密码。', developers=['OasisAkari', 'Kurisu'])


@mk.handle('<device> <month> <day> <inquiry_num> [<device_id>]')
async def mkey(msg: Bot.MessageSession, device: str, month: int, day: int, inquiry_num: str, device_id: str = None):

    device_codes = {
        "3ds": "CTR",
        "dsi": "TWL",
        "wii": "RVL",
        "wiiu": "WUP",
        "switch": "HAC"
    }

    if month < 1 or month > 12:
        await msg.finish('无效的月份。')
    if day < 1 or day > 31:
        await msg.finish('无效的日期。')

    device_code = device_codes[device.lower()]

    result = get_mkey(inquiry_num, month, day, device_id, device_code)
    await msg.finish(f'您的重置密码是：{result}。')
