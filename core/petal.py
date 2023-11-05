from datetime import datetime

from config import Config
from core.builtins import Bot
from core.utils.storedata import get_stored_list, update_stored_list

ONE_K = Decimal('1000')
# https://openai.com/pricing
BASE_COST_GPT_3_5 = Decimal('0.002')  # gpt-3.5-turbo： $0.002 / 1K tokens
# We are not tracking specific tool usage like searches b/c I'm too lazy, use a universal multiplier
THIRD_PARTY_MULTIPLIER = Decimal('1.5')
PROFIT_MULTIPLIER = Decimal('1.1')  # At the time we are really just trying to break even
PRICE_PER_1K_TOKEN = BASE_COST_GPT_3_5 * THIRD_PARTY_MULTIPLIER * PROFIT_MULTIPLIER


async def count_petal(tokens)
    USD_TO_CNY = Decimal('7.3')
    CNY_TO_PETAL = 100  # Assuming 1 USD = 7.3 CNY, 100 petal = 1 CNY

    price = tokens / ONE_K * PRICE_PER_1K_TOKEN
    petal = price * USD_TO_CNY * CNY_TO_PETAL
    return petal

def gained_petal(msg: Bot.MessageSession, amount):
    if Config('openai_api_key') and Config('enable_get_petal'):
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
                if p[msg.target.target_id]['amount'] + amount > limit:
                    return msg.locale.t('petal.message.gained.limit')
                p[msg.target.target_id]['amount'] += amount
                p = [p]
                update_stored_list(msg.target.client_name, 'gainedpetal', p)
                msg.data.modify_petal(amount)
            return msg.locale.t('petal.message.gained.success', amount=amount)


def lost_petal(msg: Bot.MessageSession, amount):
    if Config('openai_api_key') and Config('enable_get_petal'):
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
                if p[msg.target.target_id]['amount'] + amount > limit:
                    return msg.locale.t('petal.message.lost.limit')
                p[msg.target.target_id]['amount'] += amount
                p = [p]
                update_stored_list(msg.target.client_name, 'lostpetal', p)
                msg.data.modify_petal(-amount)
            return msg.locale.t('petal.message.lost.success', amount=amount)