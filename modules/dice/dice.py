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

    def Roll(self, msg, use_markdown: bool = False):
        pass


class Dice(DiceItemBase):
    """骰子项"""

    def __init__(self, msg, dice_code: str):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code)
        args = self.GetArgs(msg)
        self.count = args[0]
        self.type = args[1]
        self.adv = args[2]
        if self.count <= 0 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.m.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)
        if self.type <= 0:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.n.less_2"),
                                 self.type)
        if self.type == 1:
            raise DiceValueError(msg, msg.locale.t("dice.message.error.value.n.d1"))
        if abs(self.adv) > self.count:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.k.out_of_range"),
                                 self.adv)

    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        dice_code = dice_code.replace("D%", "D100")  # 百分骰别名
        dice_count = '1'  # 骰子数量
        advantage = '0'  # 保留的骰子量
        if re.search(r'[^0-9DKQ\%]', dice_code):
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        temp = dice_code.split('D')
        if len(temp[0]):
            dice_count = temp[0]
        dice_type = temp[1]
        if 'K' in temp[1]:
            midstrs = temp[1].partition('K')
            dice_type = midstrs[0]
            advantage = midstrs[2]
        elif 'Q' in temp[1]:
            midstrs = temp[1].partition('Q')
            dice_type = midstrs[0]
            advantage = f'-{midstrs[2]}'
        if not len(advantage.removeprefix('-')):
            advantage += '1'  # K/Q后没有值默认为1
        # 语法合法检定
        if not dice_count.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.m.invalid"),
                                 dice_count)
        if not dice_type.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.n.invalid"),
                                dice_type)
        if not (advantage.isdigit() or (advantage[0] == '-' and advantage[1:].isdigit())):
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.k.invalid"),
                                 advantage)
        return (int(dice_count), int(dice_type), int(advantage))

    def Roll(self, msg, use_markdown=False):
        output = self.code
        result = 0
        dice_results = []
        adv = self.adv
        # 生成随机序列
        for i in range(self.count):
            dice_results.append(secrets.randbelow(int(self.type)) + 1)
        if adv != 0:
            new_results = []
            indexes = np.array(dice_results).argsort()
            indexes = indexes[-adv:] if adv > 0 else indexes[:-adv]
            output += '=['
            output_buffer = ''
            for i in range(self.count):
                if use_markdown:
                    if i in indexes:
                        new_results.append(dice_results[i])
                        output_buffer += f"*{str(dice_results[i])}*"
                    else:
                        output_buffer += f"{str(dice_results[i])}"
                else:
                    output_buffer += str(dice_results[i])
                    if i in indexes:
                        new_results.append(dice_results[i])
                        output_buffer += '*'
                if i < self.count - 1:
                    output_buffer += ', '
            if self.count >= MAX_OUTPUT_CNT:
                output_buffer = msg.locale.t("dice.message.output.too_long", length=self.count)
            output += output_buffer + ']'
            dice_results = new_results
        # 公用加法
        length = len(dice_results)
        if length > 1:
            output += '=['
            if length > MAX_OUTPUT_CNT:  # 显示数据含100
                output += msg.locale.t("dice.message.output.too_long", length=length)
            for i in range(length):
                result += dice_results[i]
                if length <= MAX_OUTPUT_CNT:  # 显示数据含100
                    output += str(dice_results[i])
                    if i < length - 1:
                        output += '+'
            output += ']'
        else:
            result = dice_results[0]
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output + f"={result}"
        self.result = result


class FudgeDice(DiceItemBase):
    """命运骰子项"""

    def __init__(self, msg, dice_code: str):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code)
        args = self.GetArgs(msg)
        self.count = args[0]
        if self.count <= 0 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.m.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)


    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        if dice_code.upper().endswith('DF'):  # 兼容旧格式
            dice_code = dice_code[:-2] + 'F'
        dice_count = '4'  # 骰子数量
        if re.search(r'[^0-9F]', dice_code):
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        temp = dice_code.split('F')
        if len(temp[0]):
            dice_count = temp[0]

        # 语法合法检定
        if not dice_count.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.m.invalid"),
                                 dice_count)
        return (int(dice_count), 0)

    def Roll(self, msg, use_markdown=False):
        output = self.code
        result = 0

        dice_results = ['-', '-', '0', '0', '+', '+']
        selected_results = [secrets.choice(dice_results) for _ in range(self.count)]

        length = len(selected_results)
        output += '=['
        if length > MAX_OUTPUT_CNT:  # 显示数据含100
            output += msg.locale.t("dice.message.output.too_long", length=length)
        else:
            output += ', '.join(selected_results)
        output += ']'

        for res in selected_results:
            if res == '-':
                result -= 1
            elif res == '+':
                result += 1

        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output + f"={result}"
        self.result = result


class BonusPunishDice(DiceItemBase):
    """奖惩骰子项"""

    def __init__(self, msg, dice_code: str):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code)
        args = self.GetArgs(msg)
        self.count = args[0]
        self.positive = args[1]
        if self.count <= 0 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.m.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)

    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        if re.search(r'[^0-9BP]', dice_code):
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        if 'B' in dice_code:
            positive = False
            temp = dice_code.split('B')
            dice_count = temp[1] if len(temp[1]) else '1'  # 骰子数量
        elif 'P' in dice_code:
            positive = True
            temp = dice_code.split('P')
            dice_count = temp[1] if len(temp[1]) else '1'  # 骰子数量

        # 语法合法检定
        if not dice_count.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.m.invalid"),
                                 dice_count)

        return (int(dice_count), positive)

    def Roll(self, msg, use_markdown=False):
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
            output += '=['
            output_buffer = ''
            for i in range(self.count):
                output_buffer += str(dice_results[i])
                if i < self.count - 1:
                    output_buffer += ', '
            if self.count >= MAX_OUTPUT_CNT:
                output_buffer = msg.locale.t("dice.message.output.too_long", length=self.count)
            output += output_buffer + ']'
        else:
            output += '=' + str(dice_results[0])
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")

        if positive:
            result = max(new_results)
        else:
            result = min(new_results)

        self.detail = output
        self.result = result