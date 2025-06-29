from core.builtins import Bot, I18NContext
from core.component import module
from .process import process_expression

dice = module(
    "dice",
    alias=["rd", "roll"],
    developers=["Light-Beacon", "DoroWolf"],
    desc="{I18N:dice.help.desc}",
    doc=True,
)


@dice.command()
async def _(msg: Bot.MessageSession):
    await msg.finish(await process_expression(msg, "D", None))


@dice.command("<dices> [<dc>] {{I18N:dice.help}}")
async def _(msg: Bot.MessageSession, dices: str, dc: int = None):
    await msg.finish(await process_expression(msg, dices, dc))


@dice.command("set <sides> {{I18N:dice.help.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, sides: int):
    if sides > 1:
        await msg.target_info.edit_target_data("dice_default_sides", sides)
        await msg.finish(I18NContext("dice.message.set.success", sides=sides))
    elif sides == 0:
        await msg.target_info.edit_target_data("dice_default_sides", None)
        await msg.finish(I18NContext("dice.message.set.clear"))
    else:
        await msg.finish(I18NContext("dice.message.error.value.sides.invalid"))


@dice.command("rule {{I18N:dice.help.rule}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    dc_rule = msg.target_data.get("dice_dc_reversed")

    if dc_rule:
        await msg.target_info.edit_target_data("dice_dc_reversed", False)
        await msg.finish(I18NContext("dice.message.rule.disable"))
    else:
        await msg.target_info.edit_target_data("dice_dc_reversed", True)
        await msg.finish(I18NContext("dice.message.rule.enable"))
