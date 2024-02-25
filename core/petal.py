import os
import json
import traceback
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from config import Config
from core.builtins import Bot
from core.logger import Logger
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list

ONE_K = Decimal('1000')
# https://openai.com/pricing
BASE_COST_GPT_3_5 = Decimal('0.002')  # gpt-3.5-turbo-1106: $0.002 / 1K tokens
BASE_COST_GPT_4 = Decimal('0.03')  # gpt-4-1106-preview: $0.03 / 1K tokens
# We are not tracking specific tool usage like searches b/c I'm too lazy, use a universal multiplier
THIRD_PARTY_MULTIPLIER = Decimal('1.5')
PROFIT_MULTIPLIER = Decimal('1.1')  # At the time we are really just trying to break even
PRICE_PER_1K_TOKEN = BASE_COST_GPT_3_5 * THIRD_PARTY_MULTIPLIER * PROFIT_MULTIPLIER
PRICE_PER_1K_TOKEN_GPT_4 = BASE_COST_GPT_4 * THIRD_PARTY_MULTIPLIER * PROFIT_MULTIPLIER
USD_TO_CNY = Decimal('7.1')  # Assuming 1 USD = 7.1 CNY
CNY_TO_PETAL = 100  # 100 petal = 1 CNY


async def get_petal_exchange_rate():
    api_key = Config('exchange_rate_api_key')
    api_url = f'https://v6.exchangerate-api.com/v6/{api_key}/pair/USD/CNY'
    try:
        data = await get_url(api_url, 200, attempt=1, fmt='json', logging_err_resp=False)
        if data['result'] == "success":
            exchange_rate = data['conversion_rate']
            petal_value = exchange_rate * CNY_TO_PETAL
            return {"exchange_rate": exchange_rate, "exchanged_petal": petal_value}
    except ValueError:
        return None


async def load_or_refresh_cache():
    cache_dir = Config('cache_path')
    file_path = os.path.join(cache_dir, 'petal_exchange_rate_cache.json')
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data["exchanged_petal"]

    exchanged_petal_data = await get_petal_exchange_rate()
    if exchanged_petal_data:
        Logger.info(f'Petal exchange rate is expired or cannot be found. Updating...')
        with open(file_path, 'w') as file:
            exchanged_petal_data["update_time"] = datetime.now().strftime("%Y-%m-%d")
            json.dump(exchanged_petal_data, file)
        return exchanged_petal_data["exchanged_petal"]


async def count_petal(msg: Bot.MessageSession, tokens: int, gpt4: bool = False):
    '''计算并减少使用功能时消耗的花瓣数量。

    :param msg: 消息会话。
    :param tokens: 使用功能时花费的token数量。
    :param gpt4: 是否以GPT-4的开销计算。
    :returns: 消耗的花瓣数量，保留两位小数。
    '''
    Logger.info(f'{tokens} tokens have been consumed while calling AI.')
    if Config('enable_petal'):
        petal_exchange_rate = await load_or_refresh_cache()
        if gpt4:
            price = tokens / ONE_K * PRICE_PER_1K_TOKEN_GPT_4
        else:
            price = tokens / ONE_K * PRICE_PER_1K_TOKEN
        if petal_exchange_rate:
            petal = price * Decimal(petal_exchange_rate).quantize(Decimal('0.00'))
        else:
            Logger.warn(f'Unable to obtain real-time exchange rate, use {USD_TO_CNY} to calculate petals.')
            petal = price * USD_TO_CNY * CNY_TO_PETAL

        if Config('db_path').startswith('sqlite'):
            amount = petal.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            msg.data.modify_petal(-int(amount))
        else:
            msg.data.modify_petal(-petal)
        return round(petal, 2)
    else:
        return 0


async def gained_petal(msg: Bot.MessageSession, amount: int):
    '''增加花瓣。

    :param msg: 消息会话。
    :param amount: 增加的花瓣数量。
    :returns: 增加花瓣的提示消息。
    '''
    if Config('enable_petal') and Config('enable_get_petal'):
        limit = Config('gained_petal_limit', 10)
        p = get_stored_list(msg.target.client_name, 'gainedpetal')
        if not p:
            p = [{}]
        p = p[0]
        now = datetime.now().timestamp()
        if msg.target.target_id not in p:
            p[msg.target.target_id] = {'time': now, 'amount': amount}
            p = [p]
            update_stored_list(msg.target.client_name, 'gainedpetal', p)
            msg.data.modify_petal(amount)
            return msg.locale.t('petal.message.gained.success', amount=amount)
        else:
            if now - p[msg.target.target_id]['time'] > 60 * 60 * 24:
                p[msg.target.target_id] = {'time': now, 'amount': amount}
                p = [p]
                msg.data.modify_petal(amount)
                update_stored_list(msg.target.client_name, 'gainedpetal', p)
            else:
                if limit > 0:
                    if p[msg.target.target_id]['amount'] >= limit:
                        return msg.locale.t('petal.message.gained.limit')
                    elif p[msg.target.target_id]['amount'] + amount > limit:
                        amount = limit - p[msg.target.target_id]['amount']
                p[msg.target.target_id]['amount'] += amount
                p = [p]
                update_stored_list(msg.target.client_name, 'gainedpetal', p)
                msg.data.modify_petal(amount)
            return msg.locale.t('petal.message.gained.success', amount=amount)


async def lost_petal(msg: Bot.MessageSession, amount):
    '''减少花瓣。

    :param msg: 消息会话。
    :param amount: 减少的花瓣数量。
    :returns: 减少花瓣的提示消息。
    '''
    if Config('enable_petal') and Config('enable_get_petal'):
        limit = Config('lost_petal_limit', 5)
        p = get_stored_list(msg.target.client_name, 'lostpetal')
        if not p:
            p = [{}]
        p = p[0]
        now = datetime.now().timestamp()
        if msg.target.target_id not in p:
            p[msg.target.target_id] = {'time': now, 'amount': amount}
            p = [p]
            update_stored_list(msg.target.client_name, 'lostpetal', p)
            msg.data.modify_petal(-amount)
            return msg.locale.t('petal.message.lost.success', amount=amount)
        else:
            if now - p[msg.target.target_id]['time'] > 60 * 60 * 24:
                p[msg.target.target_id] = {'time': now, 'amount': amount}
                p = [p]
                msg.data.modify_petal(-amount)
                update_stored_list(msg.target.client_name, 'lostpetal', p)
            else:
                if limit > 0:
                    if p[msg.target.target_id]['amount'] > limit:
                        return msg.locale.t('petal.message.lost.limit')
                    elif p[msg.target.target_id]['amount'] + amount > limit:
                        amount = limit - p[msg.target.target_id]['amount']
                p[msg.target.target_id]['amount'] += amount
                p = [p]
                update_stored_list(msg.target.client_name, 'lostpetal', p)
                msg.data.modify_petal(-amount)
            return msg.locale.t('petal.message.lost.success', amount=amount)
