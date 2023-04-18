import datetime
import requests

from core.builtins import Bot
from core.component import module

exchange_rate = module('exchange_rate', required_superuser = True)

api_key = 'd31697e581d5c35b038c625c'

@exchange_rate.command('<amount> <base> <target>')
async def _(msg: Bot.MessageSession):
    base_currency = msg.parsed_msg['<base>'].upper()
    target_currency = msg.parsed_msg['<target>'].upper()

    url = f'https://v6.exchangerate-api.com/v6/{api_key}/codes'
    response = requests.get(url)
    if response.status_code == 200:
            data = response.json()
            supported_currencies = data['supported_codes']
            if base_currency not in supported_currencies:
                await msg.finish("发生错误：无效的货币单位：" + base_currency)
            elif target_currency not in supported_currencies:
                await msg.finish("发生错误：无效的货币单位：" + target_currency)
    else:
            await msg.finish(f'Error')

    amount = None
    while amount is None:
        try:
            amount = float(msg.parsed_msg['<amount>'])
            if amount <= 0:
                await msg.finish("发生错误：金额必须为正数。")
        except ValueError:
            await msg.finish("发生错误：无效的金额。")

    url = f'https://v6.exchangerate-api.com/v6/{api_key}/pair/{base_currency}/{target_currency}/{amount}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        exchange_rate = data['conversion_result']
        current_time = datetime.datetime.now().strftime("%Y-%m-%d")
        await msg.finish(f'{amount} {base_currency} -> {exchange_rate} {target_currency}\n（{current_time}）')
    else:
        await msg.finish(f'Error')
