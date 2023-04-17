import secrets
from core.builtins.message import MessageSession
from core.component import module

MAX_COIN_NUM = 10000
FACE_UP_RATE = 3333  # n/10000 
FACE_DOWN_RATE = 3333

coin_test = module('coin_test', required_superuser=True)


@coin_test.command('<amount>')
async def _(msg: MessageSession):
    amount = msg.parsed_msg.get('<amount>', '1')
    if not amount.isdigit():
        await msg.finish(msg.locale.t('coin.message.error.amount') + amount)
    else:
        await msg.finish(await flipCoins(int(amount), msg))

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
    head = msg.locale.t("coin.message", count=count)
    if count == 1:
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
