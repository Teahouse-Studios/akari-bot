from core.builtins.message import MessageSession
from core.component import module
from .dice import GenerateMessage

dice = module('dice', alias={'d4': 'dice d4', 'd6': 'dice d6',
                             'd8': 'dice d8', 'd10': 'dice d10', 'd12': 'dice d12', 'd20': 'dice d20',
                             'd100': 'dice d100'}, developers=['Light-Beacon'], desc='随机骰子',)


@dice.command('<dices> [<dc>] {投掷指定骰子,可指定投骰次数与 dc 判断判定。}',
              options_desc={
                  'dn': '表示n面骰',
                  'mdn': '表示m个n面骰，输出其所有点数之和（m若省略即为1）',
                  'mdnkx': '表示m个n面骰，输出其最大的x个骰子点数之和',
                  'mdnklx': '与上一个相同，但其会输出最小的x个骰子点数之和',
                  '多项式': '式子可以兼容多项，如“10d4-2d20”会输出10个4面骰所有点数之和减去2个20面骰点数之和',
                  '整数项': '一项可以是一个整数（也就是调节值），如“d20+5”会输出1个20面骰的点数加上5的结果',
                  '多项式最前面加 N#': '将这个式子的操作重复N次（投掷N次），之后输出N次的结果',
                  'dc': '在每一次投掷输出结果时进行判定，结果大于dc判定为成功，否则判定失败'
              })
async def _(msg: MessageSession):
    dice = msg.parsed_msg['<dices>']
    dc = msg.parsed_msg.get('<dc>', '0')
    times = '1'
    if '#' in dice:
        times = dice.partition('#')[0]
        dice = dice.partition('#')[2]
    if not times.isdigit():
        await msg.finish('发生错误：无效的投骰次数：' + times)
    if not dc.isdigit():
        await msg.finish('发生错误：无效的 dc：' + dc)
    await msg.finish(await GenerateMessage(dice, int(times), int(dc)))


@dice.regex(r"[扔|投|掷|丢]([0-9]*)?个([0-9]*面)?骰子?")
async def _(message: MessageSession):
    groups = message.matched_msg.groups()
    diceType = groups[1][:-1] if groups[1] else '6'
    await message.finish(await GenerateMessage(f'{groups[0]}D{diceType}', 1, 0))
