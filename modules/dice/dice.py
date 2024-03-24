import math
import re
import secrets

import numpy as np
from simpleeval import SimpleEval, FunctionNotDefined, NameNotDefined

from config import Config
from core.exceptions import ConfigValueError
from core.logger import Logger

# 配置常量
MAX_DICE_COUNT = Config('dice_limit', 100)  # 一次摇动最多的骰子数量
MAX_ROLL_TIMES = Config('dice_roll_limit', 10)  # 一次命令最多的摇动次数
MAX_OUTPUT_CNT = Config('dice_output_count', 50)  # 输出的最多数据量
MAX_OUTPUT_LEN = Config('dice_output_len', 200)  # 输出的最大长度
MAX_DETAIL_CNT = Config('dice_detail_count', 5)  # n次投掷的骰子的总量超过该值时将不再显示详细信息
MAX_ITEM_COUNT = Config('dice_count_limit', 10)  # 骰子表达式最多的项数

math_funcs = {
    'abs': abs,
    'ceil': math.ceil,
    'comb': math.comb,
    'exp': math.exp,
    'fabs': math.fabs,
    'factorial': math.factorial,
    'fmod': math.fmod,
    'floor': math.floor,
    'gcd': math.gcd,
    'lcm': math.lcm,
    'log': math.log,
    'log2': math.log2,
    'log10': math.log10,
    'perm': math.perm,
    'pow': math.pow,
    'sqrt': math.sqrt,
}

se = SimpleEval()
se.functions.update(math_funcs)


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
                                 msg.locale.t("dice.message.error.value.n.out_of_range", max=MAX_DICE_COUNT),
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
        else:
            dice_count = '1'
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
        output = ''
        result = 0
        dice_results = []
        adv = self.adv
        output += self.code + '='
        # 生成随机序列
        for i in range(self.count):
            dice_results.append(secrets.randbelow(int(self.type)) + 1)
        if adv != 0:
            new_results = []
            indexes = np.array(dice_results).argsort()
            indexes = indexes[-adv:] if adv > 0 else indexes[:-adv]
            output += '['
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
            output += output_buffer + ']='
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
            output += ']='
        else:
            result = dice_results[0]
        if len(output) > MAX_OUTPUT_LEN:
            output = msg.locale.t("dice.message.too_long")
        self.detail = output + f"{result}"
        self.result = result


class FudgeDice(DiceItemBase):
    """命运骰子项"""

    def __init__(self, msg, dice_code: str):
        super().__init__(dice_code)
        self.count = 4  # 默认投掷次数为4

        # 兼容旧格式
        if dice_code.upper().endswith('DF'):
            dice_code = dice_code[:-2] + 'F'
            
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
        output += self.code + '='

        dice_results = ['-', '-', '0', '0', '+', '+']
        selected_results = [secrets.choice(dice_results) for _ in range(self.count)]
        output += '[' + ', '.join(selected_results) + ']'
        
        for res in selected_results:
            if res == '-':
                result -= 1
            elif res == '+':
                result += 1

        self.detail = output + f"={result}"
        self.result = result

    def GetArgs(self, msg):
        return self.count, 6, 0


async def process_expression(msg, expr: str, times: int, dc, use_markdown = False):
    if not all([MAX_DICE_COUNT > 0, MAX_ROLL_TIMES > 0, MAX_OUTPUT_CNT > 0,
                MAX_OUTPUT_LEN > 0, MAX_DETAIL_CNT > 0, MAX_ITEM_COUNT > 0]):
        raise ConfigValueError(msg.locale.t("error.config.invalid"))
    if msg.target.sender_from in ['Discord|Client', 'Kook|User']:
        use_markdown = True
    if use_markdown:
        expr = expr.replace('*', '\*')
        expr = expr.replace('\\*', '\*')

    dice_list, count, err = parse_dice_expression(msg, expr)
    if err:
        return err
    output = generate_dice_message(msg, expr, dice_list, count, times, dc, use_markdown)
    return output

def parse_dice_expression(msg, dices):
    dice_item_list = []
    patterns = [
        r'((?:\d+)?D?F)',  # 命运骰子
        r'((?:\d+)?D(?:\d+|\%)?(?:(?:K|Q)?(?:\d+)?)?)',  # 普通骰子
        r'(\d+)',  # 数字
        r'(\(|\))',  # 括号
    ]
    errmsg = None
        
    # 切分骰子表达式
    dice_expr_list = re.split('|'.join(patterns), dices, flags=re.I)
    dice_expr_list = [item for item in dice_expr_list if item]  # 清除空白元素
    for item in range(len(dice_expr_list)):
        if dice_expr_list[item][-1].upper() == 'D' and msg.data.options.get('dice_default_face'):
            dice_expr_list[item] += str(msg.data.options.get('dice_default_face'))
    Logger.debug(dice_expr_list)

    for item in dice_expr_list:
        for pattern in patterns:
            match = re.match(pattern, item, flags=re.I)
            if match:
                dice_item_list.append(item)
                break
    if len(dice_item_list) > MAX_ITEM_COUNT:
        return None, None, DiceValueError(msg, msg.locale.t('dice.message.error.value.too_long')).message
        
    dice_count = 0
    i = 0
    # 初始化骰子序列
    for item in dice_expr_list:
        try:
            i += 1
            if 'F' in item or 'f' in item:
                dice_count += 1
                dice_expr_list[i-1] = FudgeDice(msg, item)
            elif 'D' in item or 'd' in item:
                dice_count += 1
                dice_expr_list[i-1] = Dice(msg, item)
            elif item.isdigit():
                dice_count += 1
            else:
                continue
        except (DiceSyntaxError, DiceValueError) as ex:
            errmsg = msg.locale.t('dice.message.error.prompt', i=dice_count) + ex.message
    if errmsg:
        return None, None, DiceValueError(msg, msg.locale.t('dice.message.error') + '\n' + errmsg).message
    return dice_expr_list, dice_count, None


# 在数字与数字之间加上乘号
def insert_multiply(lst, use_markdown=False):
    result = []
    asterisk = '/*' if use_markdown else '*'
    for i in range(len(lst)):
        if i == 0:
            result.append(lst[i])
        else:
            if lst[i-1][-1].isdigit() and lst[i][0].isdigit():
                result.append(asterisk)
            elif lst[i-1][-1] == ')' and lst[i][0] == '(':
                result.append(asterisk)
            elif lst[i-1][-1].isdigit() and lst[i][0] == '(':
                result.append(asterisk)
            elif lst[i-1][-1] == ')' and lst[i][0].isdigit():
                result.append(asterisk)
            result.append(lst[i])
    return result


def generate_dice_message(msg, expr, dice_expr_list, dice_count, times, dc, use_markdown=False):
    success_num = 0
    fail_num = 0
    output = msg.locale.t('dice.message.output')
    if times <= 0 or times > MAX_ROLL_TIMES:
        return DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.N.out_of_range", max=MAX_ROLL_TIMES),
                                 times).message
    # 开始投掷并生成消息
    for i in range(times):
        j = 0
        dice_detail_list = dice_expr_list.copy()
        dice_res_list = dice_expr_list.copy()
        output_line = ''
        for item in dice_detail_list:
            j += 1
            if isinstance(item, (Dice, FudgeDice)):
                item.Roll(msg, use_markdown)
                res = item.GetResult()
                if times * dice_count < MAX_DETAIL_CNT:
                    dice_detail_list[j-1] = f'({item.GetDetail()})'
                else:
                    dice_detail_list[j-1] = f'({str(res)})' if res < 0 else str(res)  # 负数加括号
                dice_res_list[j-1] = f'({str(res)})' if res < 0 else str(res)
            else:
                continue
        dice_detail_list = insert_multiply(dice_detail_list, use_markdown)
        dice_res_list = insert_multiply(dice_res_list)
        output_line += ''.join(dice_detail_list)
        Logger.debug(dice_detail_list)
        Logger.debug(dice_res_list)
        try:
            dice_res = ''.join(dice_res_list)
            dice_res = dice_res.replace('\*', '*')
            Logger.debug(dice_res)
            result = int(se.eval(dice_res))
        except (FunctionNotDefined, NameNotDefined, SyntaxError):
            return DiceSyntaxError(msg, msg.locale.t('dice.message.error.syntax')).message
        except Exception as e:
            return DiceValueError(msg, msg.locale.t('dice.message.error') + '\n' + str(e)).message
        output_line += '=' + str(result)

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
        output += f'\n{expr}={output_line}'
    if dc and times > 1:
        output += '\n' + msg.locale.t('dice.message.dc.check', success=success_num, failed=fail_num)

    return output
