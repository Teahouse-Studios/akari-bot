from core.builtins import Bot
from core.component import module
from .dice import GenerateMessage

dice = module('dice', alias=['rd', 'roll'], developers=['Light-Beacon'], desc='{dice.help.desc}')


@dice.command('<dices> [<dc>] {{dice.help}}')
async def _(msg: Bot.MessageSession, dices: str, dc = None):

    if '#' in dices:
        times = dices.partition('#')[0]
        dices = dices.partition('#')[2]
    else:
        times = '1'
    if not times.isdigit():
        await msg.finish(msg.locale.t('dice.message.N.invalid') + times)
    await msg.finish(await GenerateMessage(msg, dices, int(times), dc))


@dice.regex(r"[扔投掷擲丢]([0-9]*)?[个個]([0-9]*面)?骰子?([0-9]*次)?", desc="{dice.help.regex.desc}")
async def _(msg: Bot.MessageSession):
    groups = msg.matched_msg.groups()
    dice_type = groups[1][:-1] if groups[1] else '6'
    roll_time = groups[2][:-1] if groups[2] else '1'
    await msg.finish(await GenerateMessage(msg, f'{groups[0]}D{dice_type}', int(roll_time), None))


@dice.command('rule {{dice.help.rule}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    dc_rule = msg.data.options.get('dice_dc_reversed')

    if dc_rule:
        msg.data.edit_option('dice_dc_reversed', False)
        await msg.finish(msg.locale.t("dice.message.rule.disable"))
    else:
        msg.data.edit_option('dice_dc_reversed', True)
        await msg.finish(msg.locale.t("dice.message.rule.enable"))
