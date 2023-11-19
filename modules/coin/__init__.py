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
@coin.handle()
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
    if count > MAX_COIN_NUM:
        return msg.locale.t("coin.message.error.out_of_range", max=MAX_COIN_NUM)
    if count == 0:
        return msg.locale.t("coin.message.error.nocoin")
    if count < 0:
        return msg.locale.t("coin.message.error.amount")
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
    head = msg.locale.t("coin.message.prompt", count=count)
    if count == 1:
        if face_up:
            return head + msg.locale.t("coin.message.head")
        elif face_down:
            return head + msg.locale.t("coin.message.tail")
        else:
            return head + msg.locale.t("coin.message.stand")
    else:
        if not (stand or face_down):
            return head + msg.locale.t("coin.message.all.head")
        if not (stand or face_up):
            return head + msg.locale.t("coin.message.all.tail")
        if not (face_up or face_down):
            return head + msg.locale.t("coin.message.all.stand")
        output = head + msg.locale.t("coin.message.mix")
        if face_up:
            output += msg.locale.t("coin.message.mix.head", head=face_up)
        elif face_down:
            output += msg.locale.t("coin.message.mix.tail2", tail=face_down)
        if face_up and face_down:
            output += msg.locale.t("coin.message.mix.tail", tail=face_down)
        if stand:
            output += msg.locale.t("coin.message.mix.stand", stand=stand)
        else:
            output += msg.locale.t("message.end")
        return output


stone = module('stone', developers=['OasisAkari'], desc='{stone.help.desc}')

@stone.command()
@stone.regex(r'打水漂')
async def _(msg: Bot.MessageSession):
    '''
    if msg.target.target_from != 'TEST|Console':
        qc = CoolDown('stone', msg)
        c = qc.check(30)
        if c != 0:
            await msg.finish(msg.locale.t('message.cooldown', time=int(c), cd_time='30'))
        qc.reset()
    '''
    count = secrets.randbelow(11)
    if count == 0:
        send = msg.locale.t('stone.message.skip.nothing')
    else:
        send = msg.locale.t('stone.message.skip', count=count)

    if count == 10:
        if g := (g_msg := await gained_petal(msg, 1)):
            send += '\n' + g
    await msg.finish(send)
