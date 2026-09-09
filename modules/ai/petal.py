from decimal import Decimal
from math import ceil
from core.builtins.bot import Bot
from core.config.base import CoreConfig

PREDICT_INPUT_TOKEN = 300
PREDICT_OUTPUT_TOKEN = 200
ONE_M = Decimal("1000000")


def precount_petal(
    msg: Bot.MessageSession,
    input_price: float,
    output_price: float,
    input_tokens: int = PREDICT_INPUT_TOKEN,
    output_tokens: int = PREDICT_OUTPUT_TOKEN,
) -> bool:
    if CoreConfig.enable_petal and not msg.check_super_user():
        unit_input_price = Decimal(str(input_price)) / ONE_M
        unit_output_price = Decimal(str(output_price)) / ONE_M

        input_petal = int(ceil(input_tokens * unit_input_price))
        output_petal = int(ceil(output_tokens * unit_output_price))
        petal = input_petal + output_petal
        petal = petal if petal > 0 else 0
        if petal == 0:
            return True
        return msg.session_info.petal >= petal
    return True


async def count_token_petal(
    msg: Bot.MessageSession,
    input_price: float,
    output_price: float,
    input_tokens: int,
    output_tokens: int,
) -> int:
    if CoreConfig.enable_petal and not msg.check_super_user():
        unit_input_price = Decimal(str(input_price)) / ONE_M
        unit_output_price = Decimal(str(output_price)) / ONE_M

        input_petal = int(ceil(input_tokens * unit_input_price))
        output_petal = int(ceil(output_tokens * unit_output_price))
        petal = input_petal + output_petal
        petal = petal if petal > 0 else 0
        if petal != 0:
            await msg.session_info.sender_union_info.modify_petal(-petal)
            return petal
    return 0
