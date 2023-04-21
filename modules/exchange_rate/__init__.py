import datetime
import json

from config import Config
from core.builtins import Bot
from core.component import module
from core.exceptions import NoReportException
from core.utils.http import get_url

exchange_rate = module('exchange_rate',
                       desc='{exchange_rate.help.desc}',
                       alias={'exchangerate': 'exchange_rate',
                              'excr': 'exchange_rate'},
                       developers=['DoroWolf'])

api_key = Config('exchange_rate_api_key')


@exchange_rate.command('<base> <target> [<amount>] {{exchange_rate.help}}')
async def _(msg: Bot.MessageSession):
    base_currency = msg.parsed_msg['<base>'].upper()
    target_currency = msg.parsed_msg['<target>'].upper()

#    url = f'https://v6.exchangerate-api.com/v6/{api_key}/codes'
#    response = await get_url(url, fmt='read', status_code=200)
#    response_str = response.decode('utf-8')
#    data = json.loads(response_str)
#    supported_currencies = data['supported_codes']
#    if base_currency not in supported_currencies:
#        await msg.finish(f"{msg.locale.t('exchange_rate.message.error.invalid')}{base_currency}")
#    if target_currency not in supported_currencies:
#        await msg.finish(f"{msg.locale.t('exchange_rate.message.error.invalid')}{target_currency}")

    amount = msg.parsed_msg.get('<amount>', '1')
    try:
        amount = float(amount)
        if amount <= 0:
            await msg.finish(msg.locale.t('exchange_rate.message.error.non_positive'))
    except ValueError:
        await msg.finish(msg.locale.t('exchange_rate.message.error.non_digital'))

    url = f'https://v6.exchangerate-api.com/v6/{api_key}/pair/{base_currency}/{target_currency}/{amount}'
    response = await get_url(url, fmt='read')
    response_str = response.decode('utf-8')
    data = json.loads(response_str)
    exchange_rate = data['conversion_result']
    current_time = datetime.datetime.now().strftime("%Y-%m-%d")
    if data["result"] == "success":
       await msg.finish(
            msg.locale.t('exchange_rate.message', amount=amount, base=base_currency, exchange_rate=exchange_rate,
                         target=target_currency, time=current_time))
    else:
        error_type = data['error-type']
        raise NoReportException(f"{error_type}")
    
