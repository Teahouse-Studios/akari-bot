import secrets
import numpy as np
import re

MAX_DICE_COUNT = 100  # 一次摇动最多的骰子数量
MAX_ROLL_TIMES = 10  # 一次命令最多的摇动次数
MAX_MOD_NUMBER = 10000  # 骰子最大加权值
MIN_MOD_NUMBER = -10000  # 骰子最小加权值
MAX_OUTPUT_NUM = 50  # 输出的最多数据量
MAX_OUTPUT_LEN = 200  # 输出的最大长度
MAX_DETAIL_CNT = 5  # n次摇动的骰子的总量超过该值时将不再显示详细信息
MAX_ITEM_COUNT = 10  # 骰子多项式最多的项数


class DiceSyntaxError(Exception):
    """骰子语法错误"""

    def __init__(self, message):
        self.message = f"语法错误: {message}"


class DiceValueError(Exception):
    """骰子参数值错误"""

    def __init__(self, message, value=None):
        if value != None:
            self.message = f"参数错误: 输入为{value}，{message} "
        else:
            self.message = f"参数错误: {message} "


class DiceItemBase(object):
    """骰子项的基类"""

    def __init__(self, diceCode: str, postive: bool):
        self.postive = postive
        self.code = diceCode
        self.result = None
        self.detail = ''

    def GetResult(self, abs=True):
        if abs:
            return self.result
        else:
            return self.result if self.postive else -self.result

    def GetDetail(self):
        return self.detail

    def Roll(self):
        pass


class DiceMod(DiceItemBase):
    """调节值项"""

    def __init__(self, diceCode: str, postive: bool):
        super().__init__(diceCode, postive)
        if not diceCode.isdigit():
            raise DiceValueError(f'无效的调节值项', '+' if self.postive else '-' + diceCode)
        else:
            self.result = int(diceCode)
            if self.result > MAX_MOD_NUMBER or self.result < MIN_MOD_NUMBER:
                raise DiceValueError(f'调节值不得小于 {MIN_MOD_NUMBER} 或大于 {MIN_MOD_NUMBER}', self.result)

    def GetDetail(self):
        return self.result


class Dice(DiceItemBase):
    """骰子项"""

    def __init__(self, diceCode: str, postive: bool):
        diceCode = diceCode.replace(' ', '')
        super().__init__(diceCode, postive)
        args = self.GetArgs()
        self.count = args[0]
        self.type = args[1]
        self.adv = args[2]
        if self.count <= 0 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(f'骰子数量不得小于 1 或大于 {MAX_DICE_COUNT}', self.count)
        if self.type <= 0:
            raise DiceValueError(f'骰子面数不得小于 2', self.count)
        if self.type == 1:
            raise DiceValueError(f'1 ... 1 面的骰子？')
        if abs(self.adv) > self.count:
            raise DiceValueError(f'优劣势骰数大于总骰子数', self.adv)

    def GetArgs(self):
        diceCode = self.code.upper()  # 便于识别
        diceCount = '1'  # 骰子数量
        advantage = '0'  # 保留的骰子量
        if re.search(r'[^0-9DKL]', diceCode):
            raise DiceSyntaxError('骰子语句中存在无法识别的字符')
        if 'D' not in diceCode:
            raise DiceSyntaxError('骰子语句缺失字符 D')
        temp = diceCode.split('D')
        if len(temp[0]):
            diceCount = temp[0]
        else:
            diceCount = '1'
        midstrs = temp[1].partition('K')
        diceType = midstrs[0]
        if 'K' in midstrs[1]:
            advantage = midstrs[2].replace('L', '-')
            if not len(advantage.removeprefix('-')):
                advantage += '1'  # K/KL后没有值默认为1
        # 语法合法检定
        if not diceCount.isdigit():
            raise DiceValueError(f'无效的骰子数量', diceCount)
        if not diceType.isdigit():
            raise DiceValueError(f'无效的骰子面数', diceType)
        if not (advantage.isdigit() or (advantage[0] == '-' and advantage[1:].isdigit())):
            raise DiceValueError(f'无效的优劣势', advantage)
        return (int(diceCount), int(diceType), int(advantage))

    def Roll(self):
        output = ''
        result = 0
        diceResults = []
        adv = self.adv
        output += self.code + ' = '
        # 生成随机序列
        for i in range(self.count):
            diceResults.append(secrets.randbelow(int(self.type)) + 1)
        if adv != 0:
            newResults = []
            indexs = np.array(diceResults).argsort()
            indexs = indexs[-adv:] if adv > 0 else indexs[:-adv]
            output += '( '
            outputBuffer = ''
            for i in range(self.count):
                outputBuffer += str(diceResults[i])
                if i in indexs:
                    newResults.append(diceResults[i])
                    outputBuffer += '*'
                if i < self.count - 1:
                    outputBuffer += ','
            if self.count >= MAX_OUTPUT_NUM:
                outputBuffer = f"数量过大，已省略 {self.count} 个数据"
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
        if len(output) > MAX_OUTPUT_LEN:
            output = '输出过长...'
        self.detail = output + f" {result} "
        self.result = result


async def GenerateMessage(dices: str, times: int, dc: int):
    if re.search(r'[^0-9+-DKL]', dices.upper()):
        return DiceSyntaxError('骰子语句中存在无法识别的字符').message
    if times > MAX_ROLL_TIMES or times < 1:
        return DiceValueError(f'投骰次数不得小于 1 或 大于 {MAX_ROLL_TIMES}', times).message
    diceCodeList = re.compile(r'[+-]?[^+-]+').findall(dices)
    diceList = []
    haveErr = False
    output = ""
    diceCount = 0
    i = 0
    if len(diceCodeList) > MAX_ITEM_COUNT:
        return DiceValueError('骰子多项式项数超过限制', len(diceCodeList)).message
    # 初始化骰子序列
    for item in diceCodeList:
        i += 1
        isAdd = True
        if item[0] == '-':
            isAdd = False
            item = item[1:]
        if item[0] == '+':
            item = item[1:]
        try:
            if 'D' in item or 'd' in item:
                d = Dice(item, isAdd)
                diceList.append(d)
                diceCount += d.count
            elif item.isdigit():
                diceList.append(DiceMod(item, isAdd))
        except (DiceSyntaxError, DiceValueError) as ex:
            output += f'\n第{i}项发生{ex.message}'
            haveErr = True
    if haveErr:
        return '解析骰子多项式时存在以下错误：' + output
    successNum = 0
    failNum = 0
    output = '你掷得的结果是：'
    # 开始摇动并输出
    for i in range(times):
        outputLine = ''
        result = 0
        for dice in diceList:
            dice.Roll()
            outputLine += '+' if dice.postive else '-'
            if type(dice) is Dice and times * diceCount < MAX_DETAIL_CNT:
                outputLine += f'( {dice.GetDetail()})'
            else:
                outputLine += str(dice.GetResult())
            result += dice.GetResult(False)
        outputLine = outputLine.removeprefix('+')  # 移除多项式首个+
        outputLine += ' = ' + str(result)
        if dc != 0:
            if result > dc:
                outputLine += '，判定成功！'
                successNum += 1
            else:
                outputLine += '，判定失败！'
                failNum += 1
        output += f'\n{dices} = {outputLine}'
    if dc != 0 and times > 1:
        output += '\n▷ 判定成功数量：' + str(successNum) + '  判定失败数量：' + str(failNum)
    return output
