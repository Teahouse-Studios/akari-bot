from datetime import datetime

from config import Config
from core.builtins import Bot
from core.utils.storedata import get_stored_list, update_stored_list


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