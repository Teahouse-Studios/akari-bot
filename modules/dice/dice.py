import math
import re
import secrets

import numpy as np
from simpleeval import simple_eval

from config import Config
from core.exceptions import ConfigValueError
from core.utils.text import remove_prefix

# 配置常量
MAX_DICE_COUNT = Config('dice_limit', 100)  # 一次摇动最多的骰子数量
MAX_ROLL_TIMES = Config('dice_roll_limit', 10)  # 一次命令最多的摇动次数
MAX_MOD_NUMBER = Config('dice_mod_max', 10000)  # 骰子最大加权值
MIN_MOD_NUMBER = Config('dice_mod_min', -10000)  # 骰子最小加权值
MAX_OUTPUT_CNT = Config('dice_output_count', 50)  # 输出的最多数据量
MAX_OUTPUT_LEN = Config('dice_output_len', 200)  # 输出的最大长度
MAX_DETAIL_CNT = Config('dice_detail_count', 5)  # n次投掷的骰子的总量超过该值时将不再显示详细信息
MAX_ITEM_COUNT = Config('dice_count_limit', 10)  # 骰子表达式最多的项数


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
        self.positive = positive
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
                                 msg.locale.t("dice.message.error.value.n.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)
        if self.type <= 0:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.n.less_2"),
                                 self.count)
        if self.type == 1:
            raise DiceValueError(msg, msg.locale.t("dice.message.error.value.n.d1"))
        if abs(self.adv) > self.count:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.k.out_of_range"),
                                 self.adv)

    def GetArgs(self, msg):
        dice_code = self.code.upper()  # 便于识别
        dice_count = '1'  # 骰子数量
        advantage = '0'  # 保留的骰子量
        if re.search(r'[^0-9DKL]', dice_code):
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        temp = dice_code.split('D')
        if len(temp[0]):
            dice_count = temp[0]
        else:
            dice_count = '1'
        midstrs = temp[1].partition('K')
        dice_type = midstrs[0]
        if 'K' in midstrs[1]:
            advantage = midstrs[2].replace('L', '-')
            if not len(advantage.removeprefix('-')):
                advantage += '1'  # K/KL后没有值默认为1
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
        if msg.target.sender_from in ['Discord|Client', 'Kook|User']:
            use_markdown = True
        output = ''
        result = 0
        dice_results = []
        adv = self.adv
        output += self.code + ' = '
        # 生成随机序列
        for i in range(self.count):
            dice_results.append(secrets.randbelow(int(self.type)) + 1)
        if adv != 0:
            new_results = []
            indexes = np.array(dice_results).argsort()
            indexes = indexes[-adv:] if adv > 0 else indexes[:-adv]
            output += '('
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
                        output_buffer += '^'
                if i < self.count - 1:
                    output_buffer += ', '
            if self.count >= MAX_OUTPUT_CNT:
                output_buffer = msg.locale.t("dice.message.output.too_long", length=self.count)
            output += output_buffer + ') = '
            dice_results = new_results
        # 公用加法
        length = len(dice_results)
        if length > 1:
            output += '['
            if length > MAX_OUTPUT_CNT:  # 显示数据含100
                output += msg.locale.t("dice.message.output.too_long", length=length)
            for i in range(length):
                result += dice_results[i]
                if length <= MAX_OUTPUT_CNT:  # 显示数据含100
                    output += str(dice_results[i])
                    if i < length - 1:
                        output += '+'
            output += '] = '
        else:
            result = dice_results[0]
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output + f"{result}"
        self.result = result


class FateDice(DiceItemBase):
    """命运骰子项"""

    def __init__(self, msg, dice_code: str, positive: bool):
        super().__init__(dice_code, positive)
        self.count = 4  # 默认投掷次数为4

        # 兼容旧格式
        if dice_code.endswith('DF'):
            dice_code = dice_code[:-1] + 'F'
            
        if len(dice_code) > 1:
            try:
                self.count = int(dice_code[:-1])
            except ValueError:
                raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.invalid"))
        if self.count <= 0 or self.count > MAX_DICE_COUNT:
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.n.out_of_range", max=MAX_DICE_COUNT),
                                 self.count)

    def Roll(self, msg, use_markdown=False):
        output = ''
        result = 0
        output += self.code + ' = '

        dice_results = ['-', '-', '0', '0', '+', '+']
        selected_results = [secrets.choice(dice_results) for _ in range(self.count)]
        output += str(selected_results)
        
        for res in selected_results:
            if res == '-':
                result -= 1
            elif res == '+':
                result += 1

        self.detail = output + f" = {result}"
        self.result = result

    def GetArgs(self, msg):
        return self.count, 6, 0


async def process_expression(msg, expr: str, times: int, dc):
    if not all([MAX_DICE_COUNT > 0, MAX_ROLL_TIMES > 0, MAX_MOD_NUMBER >= MIN_MOD_NUMBER, MAX_OUTPUT_CNT > 0,
                MAX_OUTPUT_LEN > 0, MAX_DETAIL_CNT > 0, MAX_ITEM_COUNT > 0]):
        raise ConfigValueError(msg.locale.t("error.config.invalid"))
    
    dice_list = parse_dice_expression(msg, expr)
    output = generate_dice_message(dice_list, times, dc)
    return output

def parse_dice_expression(msg, dices):
    dice_item_list = []
    dice_list = []
    patterns = [
        r'(\d+)?D\d+(?:KL?(?:\d+)?)?',  # 普通骰子
        r'(\d+)?DF',  # 命运骰子
        r'\d+',  # 数字
    ]

    if re.search(r'[^0-9+\-DKLF]', dices.upper()):
        raise DiceSyntaxError(msg, msg.locale.t('dice.message.error.invalid')).message
        
    # 切分骰子表达式
    dices_expr_list = re.split('|'.join(patterns), dices)
    dices_expr_list = [item for item in dices_expr_list if item]  # 清除空白字符串

    for item in dices_expr_list:
        for pattern in patterns:
            match = re.match(pattern, item)
            if match:
                dice_item_list.append(item)
                break
    if len(dice_item_list) > MAX_ITEM_COUNT:
        raise DiceValueError(msg, msg.locale.t('dice.message.error.value.too_long'), len(dice_item_list)).message
        
    i = 0
    j = 0
    # 初始化骰子序列
    for item in dices_expr_list:
        try:
            j += 1
            if 'F' in item or 'f' in item:
                i += 1
                dices_expr_list[j-1] = FateDice(msg, item)
            elif 'D' in item or 'd' in item:
                i += 1
                dices_expr_list[j-1] = Dice(msg, item)
            elif item.isdigit():
                i += 1
            else:
                continue
        except (DiceSyntaxError, DiceValueError) as ex:
            errmsg = msg.locale.t('dice.message.error.prompt', i=i) + ex.message
    if errmsg:
        raise DiceValueError(msg, msg.locale.t('dice.message.error') + '\n' + errmsg).message
    return dice_expr_list


def generate_dice_message(expr, dice_list, times, dc):
    output = ""
    success_num = 0
    fail_num = 0
    dice_detail_list = dice_list.copy()
    # 开始投掷并生成消息
    for i in range(times):
        output_line = ''
        for item in dice_detail_list:
            if isinstance(item, (Dice, FateDice)):
                item.Roll(msg)
                if times * dice_count < MAX_DETAIL_CNT:
                    dice_detail_list[i] = f'({dice.GetDetail()})'
                else:
                    dice_detail_list[i] = str(dice.GetResult())
                dice_list[i] = str(dice.GetResult())
            else:
                continue
        output_line += ''.join(dice_detail_list)
        try:
            result = int(simple_eval(''.join(dice_list)))
        except Exception as e:
            raise DiceValueError(msg, msg.locale.t('dice.message.error') + '\n' + e).message
        output_line += ' = ' + str(result)

        if dc:
            if msg.data.options.get('dice_dc_reversed'):
                if result <= int(dc):
                    output_line += msg.locale.t('dice.message.dc.success')
                    success_num += 1
                else:
                    output_line += msg.locale.t('dice.message.dc.failed')
                    fail_num += 1
            else:
                if result >= int(dc):
                    output_line += msg.locale.t('dice.message.dc.success')
                    success_num += 1
                else:
                    output_line += msg.locale.t('dice.message.dc.failed')
                    fail_num += 1
        output += f'\n{expr} = {output_line}'
    if dc and times > 1:
        output += '\n' + msg.locale.t('dice.message.dc.check', success=str(success_num), failed=str(fail_num))
    return output
