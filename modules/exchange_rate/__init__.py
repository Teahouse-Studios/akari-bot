import datetime
import re

from core.builtins import Bot
from core.component import module
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.utils.http import get_url
from core.utils.text import isfloat

api_key = Config("exchange_rate_api_key", cfg_type=str, secret=True, table_name="module_exchange_rate")

excr = module(
    "exchange_rate",
    desc="{exchange_rate.help.desc}",
    doc=True,
    alias=["exchangerate", "exchange", "excr"],
    developers=["DoroWolf"],
)


@excr.command("<base> <target> {{exchange_rate.help}}")
async def _(msg: Bot.MessageSession, base: str, target: str):
    base = base.upper()
    target = target.upper()

    amount = base[:-3]
    base_currency = base[-3:]

    if not api_key:
        raise ConfigValueError("[I18N:error.config.secret.not_found]")

    try:
        amount = amount if amount else 1
        if float(amount) <= 0:
            await msg.finish(msg.locale.t("exchange_rate.message.invalid.non_positive"))
    except ValueError:
        await msg.finish(msg.locale.t("exchange_rate.message.invalid.non_digital"))
    await exchange(msg, base_currency, target, amount)


async def exchange(msg: Bot.MessageSession, base_currency, target_currency, amount):
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/codes"
    data = await get_url(url, 200, fmt="json")
    supported_currencies = data["supported_codes"]
    unsupported_currencies = []
    if data and data["result"] == "success":
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
            await msg.finish(
                f"{msg.locale.t("exchange_rate.message.invalid.unit")}{" ".join(unsupported_currencies)}"
            )

    url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{base_currency}/{target_currency}/{amount}"
    data = await get_url(url, 200, fmt="json")
    time = msg.ts2strftime(
        datetime.datetime.now().timestamp(), time=False, timezone=False
    )
    if data and data["result"] == "success":
        exchange_rate = data["conversion_result"]
        await msg.finish(
            msg.locale.t(
                "exchange_rate.message",
                amount=float(amount),
                base=base_currency,
                exchange_rate=exchange_rate,
                target=target_currency,
                time=time,
            )
        )


@excr.regex(
    r"(\d+(?:\.\d+)?)?\s?([a-zA-Z]{3})\s?[兑换兌換]\s?([a-zA-Z]{3})",
    mode="M",
    flags=re.I,
    desc="{exchange_rate.help.regex.desc}",
)
async def _(msg: Bot.MessageSession):
    matched_msg = msg.matched_msg
    amount = matched_msg.group(1) if matched_msg.group(1) and isfloat(matched_msg.group(1)) else 1
    base = matched_msg.group(2).upper()
    target = matched_msg.group(3).upper()
    if base != target:
        await exchange(msg, base, target, amount)
