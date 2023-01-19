import secrets

MAX_DICE_COUNT = 100  # 一次摇动最多的骰子数量
MAX_ROLL_TIMES = 10  # 一次命令最多的摇动次数
MAX_MOD_NUMBER = 10000  # 骰子最大加权值
MIN_MOD_NUMBER = -10000  # 骰子最小加权值
MAX_OUTPUT_NUM = 50  # 输出的最多数据量
MAX_OUTPUT_LEN = 200  # 输出的最大长度


async def roll(dice: str, dc: int):
    # 预处理
    dice.replace(' ', '')
    dice = dice.upper()  # 便于识别
    diceType = '*'  # 骰子面数
    diceCount = '*'  # 骰子数量
    rollTimes = '1'  # 摇动次数
    advantage = '0'  # 保留的骰子量
    mod = '0'  # Modifier
    # 语法识别
    if '*' in dice:  # 5 * 2D20K2+6 -> rollTimes
        diceArr = dice.split('*', 2)
        rollTimes = diceArr[0]
        dice = diceArr[1]
    if 'D' in dice:  # 2 D 20K2+6 -> diceCount
        diceArr = dice.split('D', 2)
        diceCount = diceArr[0]
        if diceCount == '':
            diceCount = '1'
        diceType = diceArr[1]
    else:
        diceCount = dice
        diceType = '20'
    if '+' in diceType:  # 20K2 + 6 -> mod
        diceArr = diceType.split('+', 2)
        diceType = diceArr[0]
        mod = diceArr[1]
    elif '-' in diceType:
        diceArr = diceType.split('-', 2)
        diceType = diceArr[0]
        mod = '-' + diceArr[1]
    if 'KL' in diceType:  # 20 KL 2 -> advantage
        diceArr = diceType.split('KL', 2)
        diceType = diceArr[0]
        if diceArr[1] == '':
            diceArr[1] = '1'
        advantage = '-' + diceArr[1]
    elif 'K' in diceType:
        diceArr = diceType.split('K', 2)
        diceType = diceArr[0]
        if diceArr[1] == '':
            diceArr[1] = '1'
        advantage = diceArr[1]
    # 语法合法检定
    if not diceCount.isdigit():
        return '错误：骰子数量非法:' + diceCount
    if not diceType.isdigit():
        return '错误：骰子面数非法:' + diceType
    if not rollTimes.isdigit():
        return '错误：投骰次数非法:' + rollTimes
    if not mod.removeprefix('-').isdigit():
        return '错误：调整值非法:' + mod
    if not advantage.removeprefix('-').isdigit():
        return '错误：优劣势非法:' + advantage
    # 字符串转为整型
    mod = int(mod)
    dc = int(dc)
    rollTimes = int(rollTimes)
    diceType = int(diceType)
    diceCount = int(diceCount)
    advantage = int(advantage)
    # 数值合法与防熊检定
    if (diceCount <= 0):
        return '错误：骰子数量不得小于1'
    if (diceType <= 0):
        return '错误：骰子面数不得小于1'
    if (diceCount > MAX_DICE_COUNT):
        return '错误：骰子数量过多'
    if (mod > MAX_MOD_NUMBER):
        return '错误：调整值不得大于' + str(MAX_MOD_NUMBER)
    if (mod < MIN_MOD_NUMBER):
        return '错误：调整值不得小于' + str(MIN_MOD_NUMBER)
    if (rollTimes <= 0):
        return '错误：投骰次数不得小于1'
    if (rollTimes > MAX_ROLL_TIMES):
        return '错误：投骰次数不得大于50'
    if (abs(advantage) > diceCount):
        return '错误：优劣势骰数大于总骰子数'
    # 开始随机生成
    output = '你摇出来的结果是：\n'
    successNum = 0
    failNum = 0
    for times in range(rollTimes):
        result = 0
        diceValue = 0
        diceResults = []
        output += dice + ' = '
        # 生成随机序列
        if advantage != 0:
            # 有优劣势
            output += '( '
            maxValueIndexs = []  # Index in diceResults[]
            maxValues = []
            maxValueIndex = 0  # Index in maxValues[]
            if diceCount >= MAX_OUTPUT_NUM:
                output += '数量过大省略' + str(diceCount) + '个数据'
            for i in range(diceCount):
                diceValue = secrets.randbelow(int(diceType) - 1) + 1
                diceResults.append(diceValue)
                if i < abs(advantage):
                    # 前N个直接录入
                    maxValueIndexs.append(i)
                    maxValues.append(diceValue)
                    if advantage > 0 and diceValue < maxValues[maxValueIndex]:
                        maxValueIndex = i  # 最大值列表的最小索引
                    if advantage < 0 and diceValue > maxValues[maxValueIndex]:
                        maxValueIndex = i  # 最小值列表的最大索引
                else:
                    if advantage > 0 and diceValue > maxValues[maxValueIndex]:
                        # 新大值
                        maxValueIndexs[maxValueIndex] = i
                        maxValues[maxValueIndex] = diceValue
                        maxValueIndex = maxValues.index(min(maxValues))
                    if advantage < 0 and diceValue < maxValues[maxValueIndex]:
                        # 新小值
                        maxValueIndexs[maxValueIndex] = i
                        maxValues[maxValueIndex] = diceValue
                        maxValueIndex = maxValues.index(max(maxValues))
            maxValueIndexs.append(99999)  # 加入一个不可能值，防止访问0时报错
            maxValueIndexs.sort()
            maxValues = []  # 清空以为加和做准备
            for i in range(diceCount):
                if i == maxValueIndexs[0]:
                    maxValueIndexs.pop(0)
                    maxValues.append(diceResults[i])
                    if diceCount < MAX_OUTPUT_NUM:  # 显示数据不含100
                        output += str(diceResults[i]) + '*'
                else:
                    if diceCount < MAX_OUTPUT_NUM:  # 显示数据不含100
                        output += str(diceResults[i])
                if i < diceCount-1 and diceCount < MAX_OUTPUT_NUM:  # 显示数据不含100
                    output += ' , '
            output += ' ) = '
            diceResults = maxValues
        else:
            # 无优劣势就随机生成一列
            for i in range(diceCount):
                diceResults.append(secrets.randbelow(int(diceType) - 1) + 1)
        # 公用加法
        length = len(diceResults)
        if (length > 1):
            output += '[ '
            if length > MAX_OUTPUT_NUM:  # 显示数据含100
                output += '数量过大省略' + str(length) + '个数据'
            for i in range(length):
                result += diceResults[i]
                if length <= MAX_OUTPUT_NUM:  # 显示数据含100
                    output += str(diceResults[i])
                    if i < length-1:
                        output += ' + '
            output += ' ] = '
        else:
            result = diceResults[0]
        if (mod != 0):
            output += 'N' + str(result) + ' ' + ('+' if (mod > 0)
                                                 else '-') + ' ' + str(abs(mod)) + ' = '
            result += mod
        output += str(result)
        if dc != 0:
            if result > dc:
                output += '，判定成功！'
                successNum += 1
            else:
                output += '，判定失败！'
                failNum += 1
        if (diceCount == 1 or (diceCount == 2 and (advantage != 0))) and (diceType == 20 or diceType == 100):
            temp = result - mod
            if temp >= diceType:
                output += ' 大成功！'
            if temp == 1:
                output += ' 大失败！'
        if times != rollTimes-1:
            output += '\n'
    if len(output) > MAX_OUTPUT_LEN:
        output = '输出过长...'
    if dc != 0 and rollTimes > 1:
        output += '\n▷ 判定成功数量：' + str(successNum) + '  判定失败数量：' + str(failNum)
    return output
