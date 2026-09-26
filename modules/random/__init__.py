import uuid

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.types import Param
from core.utils.random import Random
from core.utils.dirty_check import check_bool
from .choice import ask_ai_choice

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
    ai_choice = await ask_ai_choice(msg, choices)
    if ai_choice is not None:
        await msg.finish(ai_choice)
    if await check_bool(choice):
        await msg.finish(I18NContext("random.message.choice.refused"))
    await msg.finish(Random.choice(choices))


@r.command("shuffle <cards> ... {{I18N:random.help.shuffle}}")
async def _(msg: Bot.MessageSession, card: Param("<cards>", str) = None, extra_cards: Param("...", list) = None):
    cards = [card] + (extra_cards or [])
    x = Random.shuffle(cards)
    await msg.finish(", ".join(x))


@r.command("uuid {{I18N:random.help.uuid}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(str(uuid.uuid4()))
