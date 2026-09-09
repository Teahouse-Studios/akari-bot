from decimal import Decimal
from math import ceil
from core.builtins.bot import Bot
from core.config.base import CoreConfig

PREDICT_INPUT_TOKEN = 100
PREDICT_CACHE_TOKEN = 200
PREDICT_OUTPUT_TOKEN = 200
ONE_M = Decimal("1000000")


def precount_petal(
    msg: Bot.MessageSession,
    input_price: float,
    cache_price: float,
    output_price: float,
    input_tokens: int = PREDICT_INPUT_TOKEN,
    cache_tokens: int = PREDICT_CACHE_TOKEN,
    output_tokens: int = PREDICT_OUTPUT_TOKEN,
    call_price: float = 0,
) -> bool:
    if CoreConfig.enable_petal and not msg.check_super_user():
        unit_input_price = Decimal(str(input_price)) / ONE_M
        unit_cache_price = Decimal(str(cache_price)) / ONE_M
        unit_output_price = Decimal(str(output_price)) / ONE_M

        input_petal = int(ceil(input_tokens * unit_input_price))
        cache_petal = int(ceil(cache_tokens * unit_cache_price))
        output_petal = int(ceil(output_tokens * unit_output_price))
        petal = input_petal + cache_petal + output_petal + int(ceil(Decimal(str(call_price))))
        petal = petal if petal > 0 else 0
        if petal == 0:
            return True
        return msg.session_info.petal >= petal
    return True


async def count_token_petal(
    msg: Bot.MessageSession,
    input_price: float,
    cache_price: float,
    output_price: float,
    input_tokens: int,
    cache_tokens: int,
    output_tokens: int,
    call_price: float = 0,
) -> int:
    if CoreConfig.enable_petal and not msg.check_super_user():
        unit_input_price = Decimal(str(input_price)) / ONE_M
        unit_output_price = Decimal(str(output_price)) / ONE_M
        unit_cache_price = Decimal(str(cache_price)) / ONE_M

        input_petal = int(ceil(input_tokens * unit_input_price))
        cache_petal = int(ceil(cache_tokens * unit_cache_price))
        output_petal = int(ceil(output_tokens * unit_output_price))
        petal = input_petal + cache_petal + output_petal + int(ceil(Decimal(str(call_price))))
        petal = petal if petal > 0 else 0
        if petal != 0:
            await msg.session_info.sender_union_info.modify_petal(-petal)
            return petal
    return 0
