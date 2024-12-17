from core.builtins import Bot
from core.component import module
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.utils.random import Random

MAX_COIN_NUM = Config("coin_limit", 10000)
FACE_UP_WEIGHT = Config("coin_faceup_weight", 4997)
FACE_DOWN_WEIGHT = Config("coin_facedown_weight", 4997)
STAND_WEIGHT = Config("coin_stand_weight", 6)

coin = module("coin", developers=["Light-Beacon"], desc="{coin.help.desc}", doc=True)


@coin.command()
@coin.command("[<amount>] {{coin.help}}")
async def _(msg: Bot.MessageSession, amount: int = 1):
    await msg.finish(await flip_coins(amount, msg))


async def flip_coins(count: int, msg: Bot.MessageSession):
    if not all(
        [
            STAND_WEIGHT >= 0,
            FACE_UP_WEIGHT >= 0,
            FACE_DOWN_WEIGHT >= 0,
            MAX_COIN_NUM > 0,
        ]
    ):
        raise ConfigValueError(msg.locale.t("error.config.invalid"))
    if count > MAX_COIN_NUM:
        return msg.locale.t("coin.message.invalid.out_of_range", max=MAX_COIN_NUM)
    elif count < 0:
        return msg.locale.t("coin.message.invalid.amount")
    elif count == 0:
        return msg.locale.t("coin.message.nocoin")

    coin_total_weight = FACE_UP_WEIGHT + FACE_DOWN_WEIGHT + STAND_WEIGHT
    face_up = 0
    face_down = 0
    stand = 0
    for _ in range(count):
        rand_num = Random.randint(1, coin_total_weight)
        if rand_num < FACE_UP_WEIGHT:
            face_up += 1
        elif rand_num < FACE_UP_WEIGHT + FACE_DOWN_WEIGHT:
            face_down += 1
        else:
            stand += 1

    if count == 1:
        prompt = msg.locale.t("coin.message.single.prompt")
        if face_up:
            return prompt + "\n" + msg.locale.t("coin.message.single.head")
        if face_down:
            return prompt + "\n" + msg.locale.t("coin.message.single.tail")
        return prompt + "\n" + msg.locale.t("coin.message.single.stand")

    prompt = msg.locale.t("coin.message.all.prompt", count=count)
    if not (stand or face_down):
        return prompt + "\n" + msg.locale.t("coin.message.all.head")
    if not (stand or face_up):
        return prompt + "\n" + msg.locale.t("coin.message.all.tail")
    if not (face_up or face_down):
        return prompt + "\n" + msg.locale.t("coin.message.all.stand")
    output = msg.locale.t("coin.message.mix.prompt", count=count) + "\n"
    if face_up and face_down:
        output += msg.locale.t(
            "coin.message.mix.head_and_tail", head=face_up, tail=face_down
        )
    elif face_up:
        output += msg.locale.t("coin.message.mix.head", head=face_up)
    elif face_down:
        output += msg.locale.t("coin.message.mix.tail", tail=face_down)
    if stand:
        output += msg.locale.t("coin.message.mix.stand", stand=stand)
    else:
        output += msg.locale.t("message.end")
    return output
