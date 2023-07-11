import secrets

from config import Config
from core.builtins import Bot
from core.component import module
from .zhNum2Int import Zh2Int

MAX_COIN_NUM = int(Config('coin_limit'))
FACE_UP_RATE = int(Config('coin_faceup_rate'))  # n/10000
FACE_DOWN_RATE = int(Config('coin_facedown_rate'))

coin = module('coin', developers=['Light-Beacon'], desc='{coin.help.desc}')


@coin.command('{{coin.help}}')
async def _(msg: Bot.MessageSession):
    await msg.finish(await flipCoins(1, msg))


@coin.command('[<amount>] {{coin.help}}')
async def _(msg: Bot.MessageSession, amount: int = 1):
    await msg.finish(await flipCoins(amount, msg))


@coin.regex(r"[丢|抛]([^个|個|枚]*)?[个|個|枚]?硬[币|幣]", desc='{coin.help.regex.desc}')
async def _(message: Bot.MessageSession):
    groups = message.matched_msg.groups()
    count = groups[0] if groups[0] else '1'
    if count.isdigit():
        count = int(count)
    else:
        try:
            count = Zh2Int(count)
        except ValueError as ex:
            await message.finish(message.locale.t("error") + str(ex))
    await message.finish(await flipCoins(count, message))


async def flipCoins(count: int, msg):
    count_max = int(MAX_COIN_NUM)
    faceup_rate = int(FACE_UP_RATE)
    facedown_rate = int(FACE_DOWN_RATE)
    if count > count_max:
        return msg.locale.t("coin.message.error.out_of_range", max=count_max)
    if count == 0:
        return msg.locale.t("coin.message.error.nocoin")
    if count < 0:
        return msg.locale.t("coin.message.error.amount")
    if faceup_rate + facedown_rate > 10000 or faceup_rate < 0 or facedown_rate < 0 or coin_limit <= 0:
        raise OverflowError(msg.locale.t("coin.message.error.config"))
    faceUp = 0
    faceDown = 0
    stand = 0
    for i in range(count):
        randnum = secrets.randbelow(10000)
        if randnum < faceup_rate:
            faceUp += 1
        elif randnum < faceup_rate + facedown_rate:
            faceDown += 1
        else:
            stand += 1
    head = msg.locale.t("coin.message.prompt", count=count)
    if count == 1:
        if faceUp:
            return head + msg.locale.t("coin.message.head")
        elif faceDown:
            return head + msg.locale.t("coin.message.tail")
        else:
            return head + msg.locale.t("coin.message.stand")
    else:
        if not (stand or faceDown):
            return head + msg.locale.t("coin.message.all.head")
        if not (stand or faceUp):
            return head + msg.locale.t("coin.message.all.tail")
        if not (faceUp or faceDown):
            return head + msg.locale.t("coin.message.all.stand")
        output = head + msg.locale.t("coin.message.mix")
        if faceUp:
            output += msg.locale.t("coin.message.mix.head", head=faceUp)
        elif faceDown:
            output += msg.locale.t("coin.message.mix.tail2", tail=faceDown)
        if faceUp and faceDown:
            output += msg.locale.t("coin.message.mix.tail", tail=faceDown)
        if stand:
            output += msg.locale.t("coin.message.mix.stand", stand=stand)
        else:
            output += msg.locale.t("message.end")
        return output
