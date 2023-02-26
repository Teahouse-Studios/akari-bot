from core.builtins.message import MessageSession
from core.component import on_command
from .dice import roll

dice = on_command('dice', alias={'d4': 'dice d4', 'd6': 'dice d6',
                  'd8': 'dice d8', 'd10': 'dice d10', 'd12': 'dice d12', 'd20': 'dice d20'}, developers=['Light-Beacon'], desc='随机骰子',)


@dice.handle('<dices> [<dc>] {摇动指定骰子,可指定 dc 判断判定。}',)
async def _(msg: MessageSession):
    dice = msg.parsed_msg['<dices>']
    dc = msg.parsed_msg.get('<dc>', '0')
    if not dc.isdigit():
        await msg.finish('错误：DC非法:' + dc)
    await msg.finish(await roll(dice, int(dc)))
