from core.builtins import Bot
from core.component import module
from .dice import GenerateMessage

dice = module('dice', alias='rd', developers=['Light-Beacon'], desc='{dice.help.desc}', )


@dice.command('<dices> [<dc>] {{dice.help}}',
              options_desc={
                  '{dice.help.option.polynomial.title}': '{dice.help.option.polynomial}',
                  'n': '{dice.help.option.n}',
                  'm': '{dice.help.option.m}',
                  'kx': '{dice.help.option.kx}',
                  'klx': '{dice.help.option.klx}',
                  'y': '{dice.help.option.y}',
                  'N': '{dice.help.option.N}',
                  'dc': '{dice.help.option.dc}'
              })
async def _(msg: Bot.MessageSession, dices, dc='0'):
    times = '1'
    if '#' in dices:
        times = dices.partition('#')[0]
        dices = dices.partition('#')[2]
    if not times.isdigit():
        await msg.finish(msg.locale.t('dice.message.error.N.invalid') + times)
    if not dc.isdigit():
        await msg.finish(msg.locale.t('dice.message.error.dc.invalid') + dc)
    await msg.finish(await GenerateMessage(msg, dices, int(times), int(dc)))


@dice.regex(r"[扔投掷擲丢]([0-9]*)?[个個]([0-9]*面)?骰子?([0-9]*次)?", desc="{dice.help.regex.desc}")
async def _(message: Bot.MessageSession):
    groups = message.matched_msg.groups()
    dice_type = groups[1][:-1] if groups[1] else '6'
    roll_time = groups[2][:-1] if groups[2] else '1'
    await message.finish(await GenerateMessage(message, f'{groups[0]}D{dice_type}', int(roll_time), 0))


@dice.command('rule {{dice.help.rule}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    dc_rule = msg.data.options.get('dice_dc_reversed')

    if dc_rule:
        msg.data.edit_option('dice_dc_reversed', False)
        await msg.finish(msg.locale.t("dice.message.rule.disable"))
    else:
        msg.data.edit_option('dice_dc_reversed', True)
        await msg.finish(msg.locale.t("dice.message.rule.enable"))
