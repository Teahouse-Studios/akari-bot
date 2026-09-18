import uuid

from core.builtins.bot import Bot
from core.component import module
from core.types import Param
from core.utils.random import Random

r = module(
    "random",
    alias=["rand", "rng"],
    developers=["Dianliang233"],
    desc="{I18N:random.help.desc}",
    doc=True,
)


@r.command("number <minimum> <maximum> {{I18N:random.help.number}}")
async def _(msg: Bot.MessageSession, minimum: int, maximum: int):
    if minimum > maximum:
        random = Random.randint(maximum, minimum)
    else:
        random = Random.randint(minimum, maximum)

    await msg.finish("" + str(random))


@r.command("choice <choices> ... {{I18N:random.help.choice}}")
async def _(msg: Bot.MessageSession, choice: Param("<choices>", str) = None, extra_choices: Param("...", list) = None):
    choices = [choice] + (extra_choices or [])
    c = Random.choice(choices)
    await msg.finish(c)


@r.command("shuffle <cards> ... {{I18N:random.help.shuffle}}")
async def _(msg: Bot.MessageSession, card: Param("<cards>", str) = None, extra_cards: Param("...", list) = None):
    cards = [card] + (extra_cards or [])
    x = Random.shuffle(cards)
    await msg.finish(", ".join(x))


@r.command("uuid {{I18N:random.help.uuid}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(str(uuid.uuid4()))
