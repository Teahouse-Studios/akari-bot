import requests

from core.builtins import Bot
from core.component import module

exchange_rate = module('exchange_rate', required_superuser = True)

api_key = 'd31697e581d5c35b038c625c'

@exchange_rate.command('<amount> <base> <target>')
async def _(msg: Bot.MessageSession):
    base_currency = msg.parsed_msg['<base>']
    target_currency = msg.parsed_msg['<target>']
    amount = float(msg.parsed_msg['<amount>'])

    url = f'https://v6.exchangerate-api.com/v6/{api_key}/pair/{base_currency}/{target_currency}/{amount}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        exchange_rate = data['conversion_result']
        await msg.finish(f'{amount} {base_currency} -> {exchange_rate} {target_currency}')
    else:
        await msg.finish(f'Error')