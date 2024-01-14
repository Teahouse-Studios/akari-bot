import secrets

from config import Config
from core.builtins import Bot
from core.component import module
from core.petal import gained_petal, lost_petal
from core.utils.cooldown import CoolDown
from .zhNum2Int import Zh2Int

MAX_COIN_NUM = Config('coin_limit', 10000)
FACE_UP_RATE = Config('coin_faceup_rate', 4997)  # n/10000
FACE_DOWN_RATE = Config('coin_facedown_rate', 4997)

coin = module('coin', developers=['Light-Beacon'], desc='{coin.help.desc}')


@coin.command('[<amount>] {{coin.help}}')
@coin.command()
async def _(msg: Bot.MessageSession, amount: int = 1):
    await msg.finish(await flipCoins(amount, msg))


@coin.regex(r"[丢抛]([^个|個|枚]*)?[个個枚]?硬[币幣]", desc='{coin.help.regex.desc}')
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
    if FACE_UP_RATE + FACE_DOWN_RATE > 10000 or FACE_UP_RATE < 0 or FACE_DOWN_RATE < 0 or MAX_COIN_NUM <= 0:
        raise OverflowError(msg.locale.t("error.config.invalid"))
    elif count > MAX_COIN_NUM:
        return msg.locale.t("coin.message.error.out_of_range", max=MAX_COIN_NUM)
    elif count < 0:
        return msg.locale.t("coin.message.error.amount")
    elif count == 0:
        return msg.locale.t("coin.message.nocoin")

    face_up = 0
    face_down = 0
    stand = 0
    for i in range(count):
        rand_num = secrets.randbelow(10000)
        if rand_num < FACE_UP_RATE:
            face_up += 1
        elif rand_num < FACE_UP_RATE + FACE_DOWN_RATE:
            face_down += 1
        else:
            stand += 1
    if count == 1:
        prompt = msg.locale.t("coin.message.single.prompt")
        if face_up:
            return prompt + "\n" + msg.locale.t("coin.message.single.head")
        elif face_down:
            return prompt + "\n" + msg.locale.t("coin.message.single.tail")
        else:
            return prompt + "\n" + msg.locale.t("coin.message.single.stand")
    else:
        prompt = msg.locale.t("coin.message.all.prompt", count=count)
        if not (stand or face_down):
            return prompt + "\n" + msg.locale.t("coin.message.all.head")
        if not (stand or face_up):
            return prompt + "\n" + msg.locale.t("coin.message.all.tail")
        if not (face_up or face_down):
            return prompt + "\n" + msg.locale.t("coin.message.all.stand")
        output = msg.locale.t("coin.message.mix.prompt", count=count) + "\n"
        if face_up and face_down:
            output += msg.locale.t("coin.message.mix.head_and_tail", head=face_up, tail=face_down)
        elif face_up:
            output += msg.locale.t("coin.message.mix.head", head=face_up)
        elif face_down:
            output += msg.locale.t("coin.message.mix.tail", tail=face_down)
        if stand:
            output += msg.locale.t("coin.message.mix.stand", stand=stand)
        else:
            output += msg.locale.t("message.end")
        return output