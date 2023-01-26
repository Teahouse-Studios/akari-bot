from core.builtins.message import MessageSession
from core.component import on_command
from pint import UnitRegistry
from decimal import Decimal
import os

ureg = UnitRegistry(os.path.dirname(os.path.abspath(__file__)) +
                    '/default_bi_zh-cn_en.txt', non_int_type=Decimal)
# type: ignoreQ_ = ureg.Quantity

i = on_command('convert', alias=('conv', 'unit'), desc='全能单位转换。',
               developers=['Dianliang233'])


@i.handle('<from_val> <to_unit> {单位转换。大小写敏感。单位原文为英文，由 ChatGPT 翻译生成，欢迎汇报错误。}')
async def _(msg: MessageSession):
    from_val = msg.parsed_msg['<from_val>']
    to_unit = msg.parsed_msg['<to_unit>']
    ori = ureg.parse_expression(from_val)
    res = ureg.parse_expression(from_val).to(to_unit)

    await msg.finish(f"{ori:~Pg} = {res:~Pg}")
