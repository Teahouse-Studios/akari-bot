import re
import secrets

import numpy as np

from config import Config

MAX_DICE_COUNT = Config('dice_limit', 100)  # 一次摇动最多的骰子数量
MAX_OUTPUT_CNT = Config('dice_output_count', 50)  # 输出的最多数据量
MAX_OUTPUT_LEN = Config('dice_output_len', 200)  # 输出的最大长度


# 异常类定义
class DiceSyntaxError(Exception):
    """骰子语法错误"""

    def __init__(self, msg, message):
        self.message = message


class DiceValueError(Exception):
    """骰子参数值错误"""

    def __init__(self, msg, message, value=None):
        if value:
            self.message = msg.locale.t("dice.message.error.value", value=value) + message
        else:
            self.message = message


# 类定义
class DiceItemBase(object):
    """骰子项的基类"""

    def __init__(self, dice_code: str):
        self.code = dice_code
        self.result = None
        self.detail = ''

    def GetResult(self):
        return self.result

    def GetDetail(self):
        return self.detail

    def Roll(self, msg):
        pass


class Dice(DiceItemBase):
    """骰子项"""

    def __init__(self, msg, dice_code: str):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code)
        args = self.GetArgs(msg)
        self.count = args[0]
        self.sides = args[1]
        self.adv = args[2]
        self.positive = args[3]
        if self.count < 1 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)
        if self.sides < 1:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.sides.out_of_range"),
                                 self.sides)
        if self.sides == 1:
            raise DiceValueError(msg, msg.locale.t("dice.message.error.value.sides.d1"))
        if self.adv > self.count:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.advantage.out_of_range"),
                                 self.adv)

    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        dice_code = dice_code.replace("D%", "D100")  # 百分骰别名
        dice_count = '1'  # 骰子数量
        dice_adv = '0'  # 保留的骰子量
        positive = 0  # 是否保留骰子
        if re.search(r'[^0-9DKQ\%]', dice_code):
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        temp = dice_code.split('D')
        if len(temp[0]):
            dice_count = temp[0]
        dice_sides = temp[1]
        if 'K' in temp[1]:
            midstrs = temp[1].partition('K')
            dice_sides = midstrs[0]
            dice_adv = midstrs[2]
            positive = 1
        elif 'Q' in temp[1]:
            midstrs = temp[1].partition('Q')
            dice_sides = midstrs[0]
            dice_adv = midstrs[2]
            positive = -1
        if positive and not len(dice_adv):
            dice_adv = '1'  # K/Q后没有值默认为1
        # 语法合法检定
        if not dice_count.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.invalid"),
                                 dice_count)
        if not dice_sides.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.sides.invalid"),
                                dice_sides)
        if not dice_adv.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.advantage.invalid"),
                                 dice_adv)
        return (int(dice_count), int(dice_sides), int(dice_adv), positive)

    def Roll(self, msg):
        output = self.code
        result = 0
        dice_results = []
        adv = self.adv
        positive = self.positive
        # 生成随机序列
        for i in range(self.count):
            dice_results.append(secrets.randbelow(int(self.sides)) + 1)
        if adv != 0:
            new_results = []
            indexes = np.array(dice_results).argsort()
            indexes = indexes[-adv:] if positive == 1 else indexes[:adv]
            output_buffer = '=['
            for i in range(self.count):
                output_buffer += str(dice_results[i])
                if i in indexes:
                    new_results.append(dice_results[i])
                    output_buffer += '*'
                if i < self.count - 1:
                    output_buffer += ', '
            output_buffer += ']'
            if self.count >= MAX_OUTPUT_CNT:
                output_buffer = '=[' + msg.locale.t("dice.message.output.too_long", length=self.count) + ']'
            output += output_buffer
            dice_results = new_results
        # 公用加法
        length = len(dice_results)
        if length > 1:
            output_buffer = '=['
            for i in range(length):
                result += dice_results[i]
                output_buffer += str(dice_results[i])
                if i < length - 1:
                    output_buffer += '+'
            output_buffer += ']'
            if self.count > MAX_OUTPUT_CNT:  # 显示数据含100
                output_buffer = '=[' + msg.locale.t("dice.message.output.too_long", length=self.count) + ']'
            output += output_buffer
        else:
            result = dice_results[0]
        output += f'={result}'
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output 
        self.result = result


class FudgeDice(DiceItemBase):
    """命运骰子项"""

    def __init__(self, msg, dice_code: str):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code)
        args = self.GetArgs(msg)
        self.count = args[0]
        if self.count < 1 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)


    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        dice_count = '4'  # 骰子数量
        if re.search(r'[^0-9F]', dice_code):
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        temp = dice_code.split('F')
        if len(temp[0]):
            dice_count = temp[0]

        # 语法合法检定
        if not dice_count.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.invalid"),
                                 dice_count)
        return (int(dice_count), 0)

    def Roll(self, msg):
        output = self.code
        result = 0

        dice_results = ['-', '-', '0', '0', '+', '+']
        selected_results = [secrets.choice(dice_results) for _ in range(self.count)]

        if self.count > MAX_OUTPUT_CNT:  # 显示数据含100
            output_buffer = '=[' + msg.locale.t("dice.message.output.too_long", length=self.count) + ']'
        else:
            output += '=[' + ', '.join(selected_results) + ']'

        for res in selected_results:
            if res == '-':
                result -= 1
            elif res == '+':
                result += 1

        output += f'={result}'
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output 
        self.result = result


class BonusPunishDice(DiceItemBase):
    """奖惩骰子项"""

    def __init__(self, msg, dice_code: str):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code)
        args = self.GetArgs(msg)
        self.count = args[0]
        self.positive = args[1]
        if self.count < 1 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)

    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        dice_count = '1'  # 骰子数量
        if re.search(r'[^0-9BP]', dice_code):
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        if 'B' in dice_code:
            positive = False
            temp = dice_code.split('B')
            if temp[1]:
                dice_count = temp[1]
        elif 'P' in dice_code:
            positive = True
            temp = dice_code.split('P')    
            if temp[1]:
                dice_count = temp[1]

        # 语法合法检定
        if not dice_count.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.invalid"),
                                 dice_count)

        return (int(dice_count), positive)

    def Roll(self, msg):
        output = ''
        dice_results = []
        positive = self.positive
        result = 0
        # 生成随机序列

        d100_result = secrets.randbelow(100) + 1
        d100_digit = d100_result % 10
        output += f'D100={d100_result}, {self.code}'

        for i in range(self.count):
            dice_results.append(secrets.randbelow(10))

        new_results = [d100_result] + [int(str(item) + str(d100_digit)) for item in dice_results]
        new_results = [100 if item == 0 else item for item in new_results]  # 将所有00转为100

        if self.count > 1:
            if self.count >= MAX_OUTPUT_CNT:
                output_buffer = '=[' + msg.locale.t("dice.message.output.too_long", length=self.count) + ']'
            else:
                output_buffer = '=['
                for i in range(self.count):
                    output_buffer += str(dice_results[i])
                    if i < self.count - 1:
                        output_buffer += ', '
                output_buffer += ']'
            output += output_buffer
        else:
            output += '=' + str(dice_results[0])

        if positive:
            result = max(new_results)
        else:
            result = min(new_results)

        output += f'={result}'
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output 
        self.result = result


class WODDice(DiceItemBase):
    """无限骰子项"""
    def __init__(self, msg, dice_code: str):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code)
        args = self.GetArgs(msg)
        self.count = args[0]
        self.add_line = args[1]
        self.success_line = args[2]
        self.success_line_max = args[3]
        self.sides = args[4]
        if self.count < 1 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)
        if self.sides < 1:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.sides.out_of_range"),
                                 self.sides)
        if self.sides == 1:
            raise DiceValueError(msg, msg.locale.t("dice.message.error.value.sides.d1"))
        if self.add_line != 0 and (self.add_line < 2 or self.add_line > self.sides):
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.add_line.out_of_range", max=self.sides),
                                 self.add_line)

    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        match = re.match(r'(\d+)A(\d+)(?:K(\d+))?(?:Q(\d+))?(?:M(\d+))?', dice_code)
        if not match:
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        dice_count = match.group(1)  # 骰子个数
        dice_add_line = match.group(2)  # 加骰线
        dice_success_line = match.group(3) if match.group(3) else '8'  # 成功线
        dice_success_line_max = match.group(4) if match.group(4) else '0'  # 最大成功线
        dice_sides = match.group(5) if match.group(5) else '10'  # 骰子面数
        # 语法合法检定
        if not dice_count.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.invalid"),
                                 dice_count)
        if not dice_add_line.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.add_line.invalid"),
                                 dice_add_line)
        if not dice_success_line.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.dice_success_line.invalid"),
                                dice_success_line)
        if not dice_success_line_max.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.dice_success_line.invalid"),
                                dice_success_line_max)
        if not dice_sides.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.sides.invalid"),
                                dice_sides)
            
        return (int(dice_count), int(dice_add_line), int(dice_success_line), int(dice_success_line_max), int(dice_sides))

    def Roll(self, msg):
        output = self.code
        result = 0
        success_count = 0
        add_line = self.add_line
        dice_count = self.count
        success_line = self.success_line
        success_line_max = self.success_line_max
        
        output_buffer = '=['
        while dice_count:
            dice_results = []
            dice_exceed_results = []
            indexes = []
            # 生成随机序列
            for i in range(dice_count):
                dice_results.append(secrets.randbelow(int(self.sides)) + 1)
                        
                if success_line and success_line <= dice_results[i]:
                    indexes.append(i)
                if success_line_max and success_line_max >= dice_results[i]:
                    indexes.append(i)
                indexes = list(set(indexes))
                
                if add_line:
                    if dice_results[i] >= add_line:
                        dice_exceed_results.append(True)
                    else:
                        dice_exceed_results.append(False)
                else:
                    dice_exceed_results.append(False)

            exceed_result = 0
            output_buffer += '{'
            for i in range(dice_count):
                if dice_exceed_results[i]:
                    exceed_result += 1
                    output_buffer += '<'
                    output_buffer += str(dice_results[i])
                    if i in indexes:
                        success_count += 1
                        output_buffer += '*'
                    output_buffer += '>'
                else:
                    output_buffer += str(dice_results[i])
                    if i in indexes:
                        success_count += 1
                        output_buffer += '*'
                if i < dice_count - 1:
                    output_buffer += ', '
            output_buffer += '}, '
            dice_count = exceed_result
        output_buffer = output_buffer[:-2]  # 去除最后的', '
        output_buffer += ']'
        if self.count >= MAX_OUTPUT_CNT:
            output_buffer = '=[' + msg.locale.t("dice.message.output.too_long", length=self.count) + ']'
        output += output_buffer
        
        result = success_count
        output += f'={result}'
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output 
        self.result = result


class DXDice(DiceItemBase):
    """双重十字骰子项"""
    def __init__(self, msg, dice_code: str):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code)
        args = self.GetArgs(msg)
        self.count = args[0]
        self.add_line = args[1]
        self.sides = args[2]
        if self.count < 1 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)
        if self.sides < 1:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.sides.out_of_range"),
                                 self.sides)
        if self.sides == 1:
            raise DiceValueError(msg, msg.locale.t("dice.message.error.value.sides.d1"))
        if self.add_line < 2 or self.add_line > self.sides:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.add_line.out_of_range", max=self.sides),
                                 self.add_line)

    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        match = re.match(r'(\d+)C(\d+)(?:M(\d+))?', dice_code)
        if not match:
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        dice_count = match.group(1)  # 骰子个数
        dice_add_line = match.group(2)  # 加骰线
        dice_sides = match.group(3) if match.group(3) else '10'  # 骰子面数
        # 语法合法检定
        if not dice_count.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.count.invalid"),
                                 dice_count)
        if not dice_add_line.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.add_line.invalid"),
                                 dice_add_line)
        if not dice_sides.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.sides.invalid"),
                                dice_sides)
        return (int(dice_count), int(dice_add_line), int(dice_sides))

    def Roll(self, msg):
        output = self.code
        result = 0
        dice_rounds = 0
        add_line = self.add_line
        dice_count = self.count
        
        output_buffer = '=['
        while dice_count:
            dice_results = []
            dice_exceed_results = []
            dice_rounds += 1
            # 生成随机序列
            for i in range(dice_count):
                dice_results.append(secrets.randbelow(int(self.sides)) + 1)
                if dice_results[i] >= add_line:
                    dice_exceed_results.append(True)
                else:
                    dice_exceed_results.append(False)

            exceed_result = 0
            output_buffer += '{'
            for i in range(dice_count):
                if dice_exceed_results[i]:
                    exceed_result += 1
                    output_buffer += '<'
                    output_buffer += str(dice_results[i])
                    output_buffer += '>'
                else:
                    output_buffer += str(dice_results[i])
                if i < dice_count - 1:
                    output_buffer += ', '
            output_buffer += '}, '
            dice_count = exceed_result
        output_buffer = output_buffer[:-2]  # 去除最后的', '
        output_buffer += ']'
        if self.count >= MAX_OUTPUT_CNT:
            output_buffer = '=[' + msg.locale.t("dice.message.output.too_long", length=self.count) + ']'
        output += output_buffer
        
        result = (dice_rounds - 1) * self.sides + max(dice_results)
        output += f'={result}'
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output 
        self.result = result
