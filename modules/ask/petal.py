import os
from datetime import datetime
from decimal import Decimal

import orjson as json

from core.builtins import Bot
from core.config import Config
from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import get_url

ONE_K = Decimal("1000")
# https://openai.com/pricing
BASE_COST_GPT_3_5 = Decimal("0.002")  # gpt-3.5-turbo-1106: $0.002 / 1K tokens
BASE_COST_GPT_4 = Decimal("0.03")  # gpt-4-1106-preview: $0.03 / 1K tokens
# We are not tracking specific tool usage like searches b/c I'm too lazy, use a universal multiplier
THIRD_PARTY_MULTIPLIER = Decimal("1.5")
PROFIT_MULTIPLIER = Decimal(
    "1.1"
)  # At the time we are really just trying to break even
PRICE_PER_1K_TOKEN = BASE_COST_GPT_3_5 * THIRD_PARTY_MULTIPLIER * PROFIT_MULTIPLIER
PRICE_PER_1K_TOKEN_GPT_4 = BASE_COST_GPT_4 * THIRD_PARTY_MULTIPLIER * PROFIT_MULTIPLIER
USD_TO_CNY = Decimal("7.1")  # Assuming 1 USD = 7.1 CNY
CNY_TO_PETAL = 100  # 100 petal = 1 CNY


async def get_petal_exchange_rate():
    api_key = Config("exchange_rate_api_key", cfg_type=str, secret=True)
    api_url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/USD/CNY"
    try:
        data = await get_url(
            api_url, 200, attempt=1, fmt="json", logging_err_resp=False
        )
        if data["result"] == "success":
            exchange_rate = data["conversion_rate"]
            petal_value = exchange_rate * CNY_TO_PETAL
            return {"exchange_rate": exchange_rate, "exchanged_petal": petal_value}
    except ValueError:
        return None


async def load_or_refresh_cache():
    file_path = os.path.join(cache_path, "petal_exchange_rate_cache.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.loads(file.read())
            return data["exchanged_petal"]

    exchanged_petal_data = await get_petal_exchange_rate()
    if exchanged_petal_data:
        Logger.info("Petal exchange rate is expired or cannot be found. Updating...")
        with open(file_path, "wb") as file:
            exchanged_petal_data["update_time"] = datetime.now().strftime("%Y-%m-%d")
            file.write(json.dumps(exchanged_petal_data))
        return exchanged_petal_data["exchanged_petal"]


async def count_petal(msg: Bot.MessageSession, tokens: int, gpt4: bool = False):
    """计算并减少使用功能时消耗的花瓣数量。

    :param msg: 消息会话。
    :param tokens: 使用功能时花费的token数量。
    :param gpt4: 是否以GPT-4的开销计算。
    :returns: 消耗的花瓣数量，保留两位小数。
    """
    Logger.info(f"{tokens} tokens have been consumed while calling AI.")
    if Config("enable_petal", False) and not msg.check_super_user():
        petal_exchange_rate = await load_or_refresh_cache()
        if gpt4:
            price = tokens / ONE_K * PRICE_PER_1K_TOKEN_GPT_4
        else:
            price = tokens / ONE_K * PRICE_PER_1K_TOKEN
        if petal_exchange_rate:
            petal = price * Decimal(petal_exchange_rate).quantize(Decimal("0.00"))
        else:
            Logger.warning(
                f"Unable to obtain real-time exchange rate, use {USD_TO_CNY} to calculate petals."
            )
            petal = price * USD_TO_CNY * CNY_TO_PETAL

        msg.info.modify_petal(-petal)
        return round(petal, 2)
    return 0.00
