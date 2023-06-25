from core.builtins import Bot
from core.component import module
from .dice import GenerateMessage

dice = module('dice', alias={'rd': 'dice',
                             'd4': 'dice d4',
                             'd6': 'dice d6',
                             'd8': 'dice d8',
                             'd10': 'dice d10',
                             'd12': 'dice d12',
                             'd20': 'dice d20',
                             'd100': 'dice d100'}, developers=['Light-Beacon'], desc='{dice.help.desc}',)


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


@dice.regex(r"[扔|投|掷|丢]([0-9]*)?个([0-9]*面)?骰子?", desc="{dice.help.regex.desc}")
async def _(message: Bot.MessageSession):
    groups = message.matched_msg.groups()
    diceType = groups[1][:-1] if groups[1] else '6'
    await message.finish(await GenerateMessage(message, f'{groups[0]}D{diceType}', 1, 0))
