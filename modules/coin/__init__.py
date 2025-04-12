from core.builtins import Bot, I18NContext, Plain
from core.component import module
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.utils.random import Random

MAX_COIN_NUM = Config("coin_limit", 10000, table_name="module_coin")
FACE_UP_WEIGHT = Config("coin_faceup_weight", 4997, table_name="module_coin")
FACE_DOWN_WEIGHT = Config("coin_facedown_weight", 4997, table_name="module_coin")
STAND_WEIGHT = Config("coin_stand_weight", 6, table_name="module_coin")

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
        raise ConfigValueError("[I18N:error.config.invalid]")
    if count > MAX_COIN_NUM:
        return I18NContext("coin.message.invalid.out_of_range", max=MAX_COIN_NUM)
    if count < 0:
        return I18NContext("coin.message.invalid.amount")
    if count == 0:
        return I18NContext("coin.message.nocoin")

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
        prompt = [I18NContext("coin.message.single.prompt")]
        if face_up:
            prompt.append(I18NContext("coin.message.single.head"))
        elif face_down:
            prompt.append(I18NContext("coin.message.single.tail"))
        else:
            prompt.append(I18NContext("coin.message.single.stand"))
    elif sum(bool(x) for x in [face_up, face_down, stand]) == 1:
        prompt = [I18NContext("coin.message.all.prompt", count=count)]
        if not (stand or face_down):
            prompt.append(I18NContext("coin.message.all.head"))
        if not (stand or face_up):
            prompt.append(I18NContext("coin.message.all.tail"))
        if not (face_up or face_down):
            prompt.append(I18NContext("coin.message.all.stand"))
    else:
        prompt = [I18NContext("coin.message.mix.prompt", count=count)]
        output = ""
        if face_up and face_down:
            output += f"[I18N:coin.message.mix.head_and_tail,head={face_up},tail={face_down}]"
        elif face_up:
            output += f"[I18N:coin.message.mix.head,head={face_up}]"
        elif face_down:
            output += f"[I18N:coin.message.mix.tail,tail={face_down}]"
        if stand:
            output += f"[I18N:coin.message.mix.stand,stand={stand}]"
        else:
            output += "[I18N:message.end]"
        prompt.append(Plain(output))

    return prompt
