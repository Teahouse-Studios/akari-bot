from core.builtins import Bot
from core.component import module
from .process import process_expression

dice = module('dice', alias=['rd', 'roll'], developers=['Light-Beacon', 'DoroWolf'], desc='{dice.help.desc}')


@dice.command()
async def _(msg: Bot.MessageSession):
    await msg.finish(await process_expression(msg, 'D', None))


@dice.command('<dices> [<dc>] {{dice.help}}')
async def _(msg: Bot.MessageSession, dices: str, dc: int = None):
    await msg.finish(await process_expression(msg, dices, dc))


@dice.command('set <sides> {{dice.help.set}}', required_admin=True)
async def _(msg: Bot.MessageSession, sides: int):
    if sides > 1:
        msg.data.edit_option('dice_default_sides', sides)
        await msg.finish(msg.locale.t("dice.message.set.success", sides=sides))
    elif sides == 0:
        msg.data.edit_option('dice_default_sides', None)
        await msg.finish(msg.locale.t("dice.message.set.clear"))
    else:
        await msg.finish(msg.locale.t("dice.message.error.value.sides.invalid"))


@dice.command('rule {{dice.help.rule}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    dc_rule = msg.data.options.get('dice_dc_reversed')

    if dc_rule:
        msg.data.edit_option('dice_dc_reversed', False)
        await msg.finish(msg.locale.t("dice.message.rule.disable"))
    else:
        msg.data.edit_option('dice_dc_reversed', True)
        await msg.finish(msg.locale.t("dice.message.rule.enable"))
