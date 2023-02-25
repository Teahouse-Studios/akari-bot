from core.builtins.message import MessageSession
from core.component import on_command
from .dice import roll

dice = on_command('dice', alias={'d4': 'dice d4', 'd6': 'dice d6',
                  'd8': 'dice d8', 'd10': 'dice d10', 'd12': 'dice d12', 'd20': 'dice d20', 'd100': 'dice d100'}, developers=['Light-Beacon'], desc='随机骰子',)


@dice.handle('<dices> [<times>] [<dc>] {投掷指定骰子,可指定投骰次数与 dc 判断判定。}',)
async def _(msg: MessageSession):
    dice = msg.parsed_msg['<dices>']
    times = msg.parsed_msg.get('<times>', '1')
    dc = msg.parsed_msg.get('<dc>', '0')
    if not times.isdigit():
        await msg.finish('发生错误：无效的投骰次数：' + dc)
    if not dc.isdigit():
        await msg.finish('发生错误：无效的 dc：' + dc)
    await msg.finish(await GenerateMessage(dice, times, int(dc)))
    
