from core.builtins.message import MessageSession
from core.component import on_command
from .dice import roll

dice = on_command({'d20' : 'roll d20','d100' : 'roll d100','d6' : 'roll d6'}, developers=['Light-Beacon'], desc='随机骰子',)

@dice.handle('roll [<dices>] [<dc>] {摇动指定骰子,可指定 dc 判断判定。}',)
async def _(msg: MessageSession):
    dice = msg.parsed_msg.get('<dices>', "D20")
    dc = msg.parsed_msg.get('<dc>', 0)
    await msg.finish(await roll(dice,dc))