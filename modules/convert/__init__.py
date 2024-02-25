from decimal import Decimal

from pint import UnitRegistry

from core.builtins import Bot
from core.component import module

# ureg = UnitRegistry(os.path.dirname(os.path.abspath(__file__)) +
#                     '/default_bi_zh-cn_en.txt', non_int_type=Decimal)
ureg = UnitRegistry(non_int_type=Decimal)
i = module('convert', alias=['conv', 'unit'], desc='{convert.help.desc}',
           developers=['Dianliang233'], support_languages=['en_us'])


@i.command('<from_val> <to_unit> {{convert.help}}')
async def _(msg: Bot.MessageSession, from_val: str, to_unit: str):
    try:
        ori = ureg.parse_expression(from_val)
        res = ureg.parse_expression(from_val).to(to_unit)
    except BaseException:
        await msg.finish(msg.locale.t("convert.message.invalid"))

    await msg.finish(f"{ori:~Pg} = {res:~Pg}")
