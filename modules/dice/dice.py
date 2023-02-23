import secrets
import numpy as np
import re

MAX_DICE_COUNT = 100  # 一次摇动最多的骰子数量
MAX_ROLL_TIMES = 10  # 一次命令最多的摇动次数
MAX_MOD_NUMBER = 10000  # 骰子最大加权值
MIN_MOD_NUMBER = -10000  # 骰子最小加权值
MAX_OUTPUT_NUM = 50  # 输出的最多数据量
MAX_OUTPUT_LEN = 200  # 输出的最大长度


def GetDiceArgs(dice: str):
    dice.replace(' ', '')
    dice = dice.upper()  # 便于识别
    diceCount = '1'  # 骰子数量
    rollTimes = '1'  # 摇取次数
    advantage = '0'  # 保留的骰子量
    mod = '0'  # Modifier
    if 'D' not in dice:
        return '语法错误'
    temp = dice.split('D')
    if len(temp):
        if '*' in temp[0]:
            rollTimes = temp[0].split('*')[0]  # 摇动次数
            diceCount = temp[0].split('*')[1]  # 骰子数量
            dice = dice[len(rollTimes):]
        else:
            diceCount = temp[0]
    if not len(diceCount):
        diceCount = '1'
    back = re.match(r'^(.*)([+-].*)$', temp[1])
    if back:
        midstr = back.group(1)
        mod = back.group(2)
        if mod[0] == '+':
            mod = mod[1:]
    else:
        midstr = temp[1]
    midstrs = midstr.partition('K')
    diceType = midstrs[0]
    if 'K' in midstrs[1]:
        advantage = midstrs[2].replace('L', '-')
    # 语法合法检定
    if not diceCount.isdigit():
        return '发生错误：无效的骰子数量：' + diceCount
    if not diceType.isdigit():
        return '发生错误：无效的骰子面数：' + diceType
    if not rollTimes.isdigit():
        return '发生错误：无效投骰次数：' + rollTimes
    if mod[0] == '-':
        mod = mod[1:]
    if advantage[0] == '-':
        advantage = advantage[1:]
    if not mod.isdigit():
        return '发生错误：无效的调节值：' + mod
    if not advantage.isdigit():
        return '发生错误：无效的优劣势：' + advantage
    return {'times': int(rollTimes), 'cnt': int(diceCount), 'type': int(diceType), 'adv': int(advantage),
            'mod': int(mod), 'str': dice}


def RollDice(args, dc):
    output = '你掷得的结果是：\n'
    successNum = 0
    failNum = 0
    for times in range(args['times']):
        result = 0
        diceResults = []
        output += args['str'] + ' = '
        # 生成随机序列
        for i in range(args['cnt']):
            diceResults.append(secrets.randbelow(int(args['type']) - 1) + 1)
        if args['adv'] != 0:
            newResults = []
            indexs = np.array(diceResults).argsort()
            indexs = indexs[-args['adv']:] if args['adv'] > 0 else indexs[:-args['adv']]
            output += '( '
            outputBuffer = ''
            for i in range(args['cnt']):
                outputBuffer += str(diceResults[i])
                if i in indexs:
                    newResults.append(diceResults[i])
                    outputBuffer += '*'
                if i < args['cnt'] - 1:
                    outputBuffer += ','
            if args['cnt'] >= MAX_OUTPUT_NUM:
                outputBuffer = f"数量过大，已省略 {args['cnt']} 个数据"
            output += outputBuffer + ' ) = '
            diceResults = newResults
        # 公用加法
        length = len(diceResults)
        if (length > 1):
            output += '[ '
            if length > MAX_OUTPUT_NUM:  # 显示数据含100
                output += f'数量过大，已省略 {length} 个数据'
            for i in range(length):
                result += diceResults[i]
                if length <= MAX_OUTPUT_NUM:  # 显示数据含100
                    output += str(diceResults[i])
                    if i < length - 1:
                        output += '+'
            output += ' ] = '
        else:
            result = diceResults[0]
        # Modifier
        if args['mod'] != 0:
            output += f"N{result}"
            if args['mod'] > 0:
                output += '+'
            output += f"{args['mod']} = "
        output += str(result)
        if dc != 0:
            if result > dc:
                output += '，判定成功！'
                successNum += 1
            else:
                output += '，判定失败！'
                failNum += 1
        if (args['cnt'] == 1 or (args['cnt'] == 2 and (args['adv'] != 0))) and (
            args['type'] == 20 or args['type'] == 100) and args['mod'] >= 0:
            temp = result - args['mod']
            if temp >= args['type']:
                output += ' 大成功！'
            if temp == 1:
                output += ' 大失败！'
        if times != args['times'] - 1:
            output += '\n'
    if len(output) > MAX_OUTPUT_LEN:
        output = '输出过长...'
    if dc != 0 and args['times'] > 1:
        output += '\n▷ 判定成功数量：' + str(successNum) + '  判定失败数量：' + str(failNum)
    return output


async def roll(dice: str, dc: int):
    diceArgs = GetDiceArgs(dice)  # 语法识别
    if type(diceArgs) is str:
        return diceArgs  # 报错输出
    if diceArgs['times'] <= 0 or diceArgs['times'] > MAX_ROLL_TIMES:
        return f'发生错误：投骰次数不得小于 1 或 大于 {MAX_ROLL_TIMES}'
    if diceArgs['cnt'] <= 0 or diceArgs['cnt'] > MAX_DICE_COUNT:
        return f'发生错误：骰子数量不得小于 1 或大于 {MAX_DICE_COUNT}'
    if diceArgs['type'] <= 0:
        return '发生错误：骰子面数不得小于 1'
    if abs(diceArgs['adv']) > diceArgs['cnt']:
        return '发生错误：优劣势骰数大于总骰子数'
    if diceArgs['mod'] > MAX_MOD_NUMBER or diceArgs['mod'] < MIN_MOD_NUMBER:
        return f'发生错误：调节值不得小于 {MIN_MOD_NUMBER} 或大于 {MIN_MOD_NUMBER} '
    # 开始随机生成
    return RollDice(diceArgs, dc)
