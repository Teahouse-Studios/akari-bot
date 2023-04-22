import re
import secrets

import numpy as np
from core.builtins import Bot

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

    def __init__(self, message, msg: Bot.MessageSession):
        self.message = f"{msg.locale.t('dice.message.error.syntax')}{message}"


class DiceValueError(Exception):
    """骰子参数值错误"""

    def __init__(msg: Bot.MessageSession, self, message, value=None):
        if value != None:
            self.message = f"{msg.locale.t('dice.message.error.value.invalid', value=value)}{message} "
        else:
            self.message = f"{msg.locale.t('dice.message.error.value')}{message} "


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

    def __init__(self, diceCode: str, postive: bool, msg: Bot.MessageSession):
        super().__init__(diceCode, postive)
        if not diceCode.isdigit():
            raise DiceValueError(msg.locale.t('dice.message.error.value.M.invalid'), '+' if self.postive else '-' + diceCode)
        else:
            self.result = int(diceCode)
            if self.result > MAX_MOD_NUMBER or self.result < MIN_MOD_NUMBER:
                raise DiceValueError(msg.locale.t('dice.message.error.value.M.out_of_range', min=MIN_MOD_NUMBER, max=MAX_MOD_NUMBER), self.result)

    def GetDetail(self):
        return self.result


class Dice(DiceItemBase):
    """骰子项"""

    def __init__(self, diceCode: str, postive: bool, msg: Bot.MessageSession):
        diceCode = diceCode.replace(' ', '')
        super().__init__(diceCode, postive)
        args = self.GetArgs()
        self.count = args[0]
        self.type = args[1]
        self.adv = args[2]
        if self.count <= 0 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg.locale.t('dice.message.error.value.n.out_of_range', max=MAX_DICE_COUNT), self.count)
        if self.type <= 0:
            raise DiceValueError(msg.locale.t('dice.message.error.value.n.less2'), self.count)
        if self.type == 1:
            raise DiceValueError(msg.locale.t('dice.message.error.value.n.d1'))
        if abs(self.adv) > self.count:
            raise DiceValueError(msg.locale.t('dice.message.error.value.k.out_of_range'), self.adv)

    def GetArgs(self, msg: Bot.MessageSession):
        diceCode = self.code.upper()  # 便于识别
        diceCount = '1'  # 骰子数量
        advantage = '0'  # 保留的骰子量
        if re.search(r'[^0-9DKL]', diceCode):
            raise DiceSyntaxError(msg.locale.t('dice.message.error.syntax.invalid'))
        if 'D' not in diceCode:
            raise DiceSyntaxError(msg.locale.t('dice.message.error.syntax.missing_d'))
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
            raise DiceValueError(msg.locale.t('dice.message.error.value.m.invalid'), diceCount)
        if not diceType.isdigit():
            raise DiceValueError(msg.locale.t('dice.message.error.value.n.invalid'), diceType)
        if not (advantage.isdigit() or (advantage[0] == '-' and advantage[1:].isdigit())):
            raise DiceValueError(msg.locale.t('dice.message.error.value.k.invalid'), advantage)
        return (int(diceCount), int(diceType), int(advantage))

    def Roll(self, msg: Bot.MessageSession):
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
                outputBuffer = msg.locale.t('dice.message.count.too_long', count=self.count)
            output += outputBuffer + ' ) = '
            diceResults = newResults
        # 公用加法
        length = len(diceResults)
        if (length > 1):
            output += '[ '
            if length > MAX_OUTPUT_NUM:  # 显示数据含100
                output += msg.locale.t('dice.message.output.too_long', length=length)
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
            output = msg.locale.t('dice.message.too_long')
        self.detail = output + f" {result} "
        self.result = result


async def GenerateMessage(dices: str, times: int, dc: int, msg: Bot.MessageSession):
    if re.search(r'[^0-9+\-DKL]', dices.upper()):
        return DiceSyntaxError(msg.locale.t('dice.message.error.syntax.invalid')).message
    if times > MAX_ROLL_TIMES or times < 1:
        return DiceValueError(msg.locale.t('dice.message.error.value.N.out_of_range', max=MAX_ROLL_TIMES), times).message
    diceCodeList = re.compile(r'[+-]?[^+-]+').findall(dices)
    diceList = []
    haveErr = False
    output = ""
    diceCount = 0
    i = 0
    if len(diceCodeList) > MAX_ITEM_COUNT:
        return DiceValueError(msg.locale.t('dice.message.error.value.too_long'), len(diceCodeList)).message
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
            output += f"\n{msg.locale.t('dice.message.error.prompt', i=i)}{ex.message}"
            haveErr = True
    if haveErr:
        return msg.locale.t('dice.message.error') + output
    successNum = 0
    failNum = 0
    output = msg.locale.t('dice.message.output')
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
                outputLine += msg.locale.t('dice.message.dc.failed')
                successNum += 1
            else:
                outputLine += msg.locale.t('dice.message.dc.success')
                failNum += 1
        output += f'\n{dices} = {outputLine}'
    if dc != 0 and times > 1:
        output += '\n' + msg.locale.t('dice.message.dc.check', success=str(successNum), failed=str(failNum))
    return output
