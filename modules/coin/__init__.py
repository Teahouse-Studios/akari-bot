import secrets
from core.builtins.message import MessageSession
from core.component import module
from .zhNum2Int import Zh2Int

MAX_COIN_NUM = 100
FACE_UP_RATE = 4994  # n/10000 
FACE_DOWN_RATE = 4994
COIN_DROP_PLACES = ["地上", "桌子上", "桌子底下", "门口", "窗户外", "月球"]  # 硬币可能掉落的位置

coin = module('coin', developers=['Light-Beacon'], desc='{coin.help.desc}')


@coin.command('<amount> {{coin.help}}')
async def _(msg: MessageSession):
    amount = msg.parsed_msg.get('<amount>', '1')
    if not amount.isdigit():
        await msg.finish(msg.locale.t('coin.message.error.amount') + amount)
    else:
        await msg.finish(await flipCoins(int(amount)))


@coin.regex(r"[丢|抛]([^个|枚]*)?[个|枚]?硬币", desc='[丢/抛](n)[个/枚]?硬币')
async def _(message: MessageSession):
    groups = message.matched_msg.groups()
    count = groups[0] if groups[0] else '1'
    if count.isdigit():
        count = int(count)
    else:
        try:
            count = Zh2Int(count)
        except ValueError as ex:
            await message.finish(message.locale.t("error") + str(ex))
    await message.finish(await flipCoins(count, msg=message))


async def flipCoins(count: int, msg):
    if count > MAX_COIN_NUM:
        return msg.locale.t("coin.message.error.max", max=MAX_COIN_NUM)
    if count <= 0:
        return msg.locale.t("coin.message.error.nocoin")
    if FACE_UP_RATE + FACE_DOWN_RATE > 10000 or FACE_UP_RATE < 0 or FACE_DOWN_RATE < 0:
        raise OverflowError(msg.locale.t("coin.message.error.rate"))
    faceUp = 0
    faceDown = 0
    stand = 0
    for i in range(count):
        randnum = secrets.randbelow(10000)
        if randnum < FACE_UP_RATE:
            faceUp += 1
        elif randnum < FACE_UP_RATE + FACE_DOWN_RATE:
            faceDown += 1
        else:
            stand += 1
    head = msg.locale.t("coin.message")
    if count == 1:
        drop_place = COIN_DROP_PLACES[secrets.randbelow(len(COIN_DROP_PLACES))]
        head += msg.locale.t("coin.message.drop_place", drop_place=drop_place) + '\n'
        if faceUp:
            return head + msg.locale.t("coin.message.head")
        elif faceDown:
            return head + msg.locale.t("coin.message.tail")
        else:
            return head + msg.locale.t("coin.message.stand")
    else:
        if not (stand or faceDown):
            return head + msg.locale.t("coin.message.head.all")
        if not (stand or faceUp):
            return head + msg.locale.t("coin.message.tail.all")
        if not (faceUp or faceDown):
            return head + msg.locale.t("coin.message.stand.all")
        output = head + msg.locale.t("coin.message.mix")
        if faceUp:
            output += msg.locale.t("coin.message.mix.head", head=faceUp)
        if faceDown:
            output += msg.locale.t("coin.message.mix.tail", tail=faceDown)
        if stand:
            output += msg.locale.t("coin.message.mix.stand", stand=stand)
        else:
            output += msg.locale.t("coin.message.mix.end")
        return output
