import datetime

from config import Config
from core.builtins import Bot
from core.component import module
from core.exceptions import ConfigValueError
from core.utils.http import get_url

api_key = Config('exchange_rate_api_key')

excr = module('exchange_rate',
              desc='{exchange_rate.help.desc}',
              alias=['exchangerate', 'excr'],
              developers=['DoroWolf'])


@excr.command('<base> <target> {{exchange_rate.help}}')
async def _(msg: Bot.MessageSession, base: str, target: str):
    base = base.upper()
    target = target.upper()

    amount_str = base[:-3]
    base_currency = base[-3:]

    if not api_key:
        raise ConfigValueError(msg.locale.t('error.config.secret.not_found'))

    try:
        if amount_str:
            amount = float(amount_str)
        else:
            amount = 1.0

        if amount <= 0:
            await msg.finish(msg.locale.t('exchange_rate.message.error.non_positive'))
    except ValueError:
        await msg.finish(msg.locale.t('exchange_rate.message.error.non_digital'))
    await msg.finish(await exchange(base_currency, target, amount, msg))


async def exchange(base_currency, target_currency, amount: float, msg):
    url = f'https://v6.exchangerate-api.com/v6/{api_key}/codes'
    data = await get_url(url, 200, fmt='json')
    supported_currencies = data['supported_codes']
    unsupported_currencies = []
    if data['result'] == "success":
        for currencie_names in supported_currencies:
            if base_currency in currencie_names:
                break
        else:
            unsupported_currencies.append(base_currency)
        for currencie_names in supported_currencies:
            if target_currency in currencie_names:
                break
        else:
            unsupported_currencies.append(target_currency)
        if unsupported_currencies:
            await msg.finish(f"{msg.locale.t('exchange_rate.message.error.unit')}{' '.join(unsupported_currencies)}")
    else:
        raise Exception(data['error-type'])

    url = f'https://v6.exchangerate-api.com/v6/{api_key}/pair/{base_currency}/{target_currency}/{amount}'
    data = await get_url(url, 200, fmt='json')
    time = msg.ts2strftime(datetime.datetime.now().timestamp(), time=False, timezone=False)
    if data['result'] == "success":
        exchange_rate = data['conversion_result']
        await msg.finish(
            msg.locale.t('exchange_rate.message',
                         amount=amount,
                         base=base_currency,
                         exchange_rate=exchange_rate,
                         target=target_currency,
                         time=time))
    else:
        raise Exception(data['error-type'])


@excr.regex(r"(\d+(\.\d+)?)?\s?([a-zA-Z]{3})\s?[兑换兌換]\s?([a-zA-Z]{3})", desc='{exchange_rate.help.regex.desc}')
async def _(msg: Bot.MessageSession):
    groups = msg.matched_msg.groups()
    amount = groups[0] if groups[0] else '1'
    base = groups[2].upper()
    target = groups[3].upper()
    if base != target:
        await msg.finish(await exchange(base, target, amount, msg))
