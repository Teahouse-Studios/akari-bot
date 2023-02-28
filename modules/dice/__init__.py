from core.builtins.message import MessageSession
from core.component import on_command, on_regex
from .dice import GenerateMessage

dice = on_command('dice', alias={'d4': 'dice d4', 'd6': 'dice d6',
                  'd8': 'dice d8', 'd10': 'dice d10', 'd12': 'dice d12', 'd20': 'dice d20', 'd100': 'dice d100'}, developers=['Light-Beacon'], desc='随机骰子', recommend_modules=['dice_regex'])


@dice.handle('<dices> [<dc>] {投掷指定骰子,可指定投骰次数与 dc 判断判定。}',)
async def _(msg: MessageSession):
    dice = msg.parsed_msg['<dices>']
    dc = msg.parsed_msg.get('<dc>', '0')
    if '#' in dice:
        times = dice.partition('#')[0]
        dice = dice.partition('#')[2]
        if not times.isdigit():
            await msg.finish('发生错误：无效的投骰次数：' + times)
    if not dc.isdigit():
        await msg.finish('发生错误：无效的 dc：' + dc)
    await msg.finish(await GenerateMessage(dice, int(times), int(dc)))

dicergex = on_regex('dice_regex',
                  desc='打开后将在发送的聊天内容匹配以下信息时执行对应命令：\n'
                       '[扔投骰丢](N)个(n面)骰(子)', developers=['Light-Beacon'])

@dicergex.handle(r"[扔|投|掷|丢]([0-9]*)?个([0-9]*面)?骰子?")
async def _(message: MessageSession):
    groups = message.matched_msg.groups()
    diceType = groups[1][:-1] if groups[1] else '6'
    await message.finish(await GenerateMessage(f'{groups[0]}D{diceType}',1,0))
