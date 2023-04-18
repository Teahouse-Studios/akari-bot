import datetime
import requests

from core.builtins import Bot
from core.component import module

exchange_rate = module('exchange_rate', required_superuser = True)

api_key = 'd31697e581d5c35b038c625c'

@exchange_rate.command('<amount> <base> <target>')
async def _(msg: Bot.MessageSession):
    base_currency = msg.parsed_msg['<base>']
    target_currency = msg.parsed_msg['<target>']
    amount = None
    while amount is None:
        try:
            amount = float(msg.parsed_msg['<amount>'])
            if amount <= 0:
                raise ValueError("发生错误：金额必须为正数。")
        except ValueError:
            await msg.finish("发生错误：无效的金额。")

    url = f'https://v6.exchangerate-api.com/v6/{api_key}/pair/{base_currency}/{target_currency}/{amount}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        exchange_rate = data['conversion_result']
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await msg.finish(f'{amount} {base_currency} -> {exchange_rate} {target_currency}\n（{current_time}）')
    else:
        await msg.finish(f'Error')
