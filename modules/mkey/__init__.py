from core.component import module
from core.builtins import Bot
from .generator import get_mkey

mk = module('mkey', desc='{mkey.help.desc}', developers=['OasisAkari', 'Kurisu'])


@mk.command('<device> <month> <day> <inquiry_num> [<device_id>]')
async def mkey(msg: Bot.MessageSession, device: str, month: int, day: int, inquiry_num: str, device_id: str = None):

    device_codes = {
        "3ds": "CTR",
        "dsi": "TWL",
        "wii": "RVL",
        "wiiu": "WUP",
        "switch": "HAC"
    }

    if month < 1 or month > 12:
        await msg.finish(msg.locale.t('mkey.message.error.date.month'))
    if day < 1 or day > 31:
        await msg.finish(msg.locale.t('mkey.message.error.date.day'))
    if device.lower() not in device_codes:
        await msg.finish(msg.locale.t('mkey.message.error.device'))
    if len(inquiry_num) not in [6, 8, 10]:
        await msg.finish(msg.locale.t('mkey.message.error.inquiry_num'))
    device_code = device_codes[device.lower()]
    if device_id is None and device_code == "HAC":
        await msg.finish(msg.locale.t('mkey.message.error.hal'))

    result = get_mkey(inquiry_num, month, day, device_id, device_code)
    await msg.finish(msg.locale.t('mkey.message.result', result=result))
