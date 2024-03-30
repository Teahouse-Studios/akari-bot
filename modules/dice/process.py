import math
import re

from simpleeval import SimpleEval, FunctionNotDefined, NameNotDefined

from config import Config
from core.exceptions import ConfigValueError
from core.logger import Logger
from .dice import *

# 配置常量
MAX_DICE_COUNT = Config('dice_limit', 100)  # 一次摇动最多的骰子数量
MAX_ROLL_TIMES = Config('dice_roll_limit', 10)  # 一次命令最多的摇动次数
MAX_OUTPUT_CNT = Config('dice_output_count', 50)  # 输出的最多数据量
MAX_OUTPUT_LEN = Config('dice_output_len', 200)  # 输出的最大长度
MAX_DETAIL_CNT = Config('dice_detail_count', 5)  # n次投掷的骰子的总量超过该值时将不再显示详细信息
MAX_ITEM_COUNT = Config('dice_count_limit', 10)  # 骰子表达式最多的项数

dice_patterns = [
    r'(\d+A\d+(?:[KQM]?\d*)?(?:[KQM]?\d*)?(?:[KQM]?\d*)?)',  # WOD骰子
    r'(\d+C\d+M?\d*)',  # 双重十字骰子
    r'(?:D(?:100|%)?)?([BP]\d*)',  # 奖惩骰子
    r'D?(\d*F)',  # 命运骰子
    r'(\d*D\d*%?(?:K\d*|Q\d*)?)',  # 普通骰子
    r'(\d+)',  # 数字
    r'([\(\)])',  # 括号
]

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
    'perm': math.perm,
    'pow': math.pow,
    'sqrt': math.sqrt,
}

se = SimpleEval()
se.functions.update(math_funcs)


async def process_expression(msg, expr: str, dc, use_markdown=False):
    if not all([MAX_DICE_COUNT > 0, MAX_ROLL_TIMES > 0, MAX_OUTPUT_CNT > 0,
                MAX_OUTPUT_LEN > 0, MAX_DETAIL_CNT > 0, MAX_ITEM_COUNT > 0]):
        raise ConfigValueError(msg.locale.t("error.config.invalid"))
    if msg.target.sender_from in ['Discord|Client', 'Kook|User']:
        use_markdown = True
    if use_markdown:
        expr = expr.replace('*', '\\*')
        expr = expr.replace(r'\\*', '\\*')

    dice_list, count, times, err = parse_dice_expression(msg, expr)
    if err:
        return err
    output = generate_dice_message(msg, expr, dice_list, count, times, dc, use_markdown)
    return output


def parse_dice_expression(msg, dices):
    dice_item_list = []
    math_func_pattern = '(' + '|'.join(re.escape(func) for func in math_funcs.keys()) + ')'  # 数学函数
    errmsg = None

    # 切分骰子表达式
    if '#' in dices:
        times = dices.partition('#')[0]
        dices = dices.partition('#')[2]
    else:
        times = '1'
    if not times.isdigit():
        errmsg = msg.locale.t('dice.message.error.value.times.invalid')
        return None, None, None, DiceValueError(msg, msg.locale.t('dice.message.error') + '\n' + errmsg).message

    dice_expr_list = re.split(f'{math_func_pattern}|' + '|'.join(dice_patterns), dices, flags=re.I)
    dice_expr_list = [item for item in dice_expr_list if item]  # 清除空白元素
    for item in range(len(dice_expr_list)):
        if dice_expr_list[item][-1].upper() == 'D' and dice_expr_list[item] not in math_funcs.keys()\
                and msg.data.options.get('dice_default_sides'):
            dice_expr_list[item] += str(msg.data.options.get('dice_default_sides'))

    for i, item in enumerate(dice_expr_list):  # 将所有骰子项切片转为大写
        for pattern in dice_patterns:
            match = re.match(pattern, item, flags=re.I)
            if match:
                dice_expr_list[i] = item.upper()
                dice_item_list.append(item)
                break
        # 将所有数学函数切片转为小写
        func_match = re.match(math_func_pattern, item, flags=re.I)
        if func_match:
            dice_expr_list[i] = item.lower()

    Logger.debug(dice_expr_list)
    if len(dice_item_list) > MAX_ITEM_COUNT:
        errmsg = msg.locale.t('dice.message.error.value.too_long')
        return None, None, None, DiceValueError(msg, msg.locale.t('dice.message.error') + errmsg).message

    dice_count = 0
    # 初始化骰子序列
    for j, item in enumerate(dice_expr_list):
        try:
            if any(item.lower() == func for func in math_funcs.keys()):
                continue
            elif 'A' in item:
                dice_count += 1
                dice_expr_list[j] = WODDice(msg, item)
            elif 'C' in item:
                dice_count += 1
                dice_expr_list[j] = DXDice(msg, item)
            elif 'B' in item or 'P' in item:
                dice_count += 1
                dice_expr_list[j] = BonusPunishDice(msg, item)
            elif 'F' in item:
                dice_count += 1
                dice_expr_list[j] = FudgeDice(msg, item)
            elif 'D' in item:
                dice_count += 1
                dice_expr_list[j] = Dice(msg, item)
            elif item.isdigit():
                dice_count += 1
        except (DiceSyntaxError, DiceValueError) as ex:
            errmsg = msg.locale.t('dice.message.error.prompt', i=dice_count) + ex.message
    if errmsg:
        return None, None, None, DiceValueError(msg, msg.locale.t('dice.message.error') + '\n' + errmsg).message
    return dice_expr_list, dice_count, int(times), None

# 在数字与数字之间加上乘号


def insert_multiply(lst, use_markdown=False):
    result = []
    asterisk = '/*' if use_markdown else '*'
    for i in range(len(lst)):
        if i == 0:
            result.append(lst[i])
        else:
            if lst[i - 1][-1].isdigit() and lst[i][0].isdigit():
                result.append(asterisk)
            elif lst[i - 1][-1] == ')' and lst[i][0] == '(':
                result.append(asterisk)
            elif lst[i - 1][-1].isdigit() and lst[i][0] == '(':
                result.append(asterisk)
            elif lst[i - 1][-1] == ')' and lst[i][0].isdigit():
                result.append(asterisk)
            result.append(lst[i])
    return result

# 开始投掷并生成消息


def generate_dice_message(msg, expr, dice_expr_list, dice_count, times, dc, use_markdown=False):
    success_num = 0
    fail_num = 0
    output = msg.locale.t('dice.message.output')
    if '#' in expr:
        expr = expr.partition('#')[2]
    if times < 1 or times > MAX_ROLL_TIMES:
        errmsg = msg.locale.t('dice.message.error.value.times.out_of_range', max=MAX_ROLL_TIMES)
        return DiceValueError(msg, msg.locale.t('dice.message.error') + '\n' + errmsg).message

    for _ in range(times):
        dice_detail_list = dice_expr_list.copy()
        dice_res_list = dice_expr_list.copy()
        output_line = ''
        for i, item in enumerate(dice_detail_list):
            if isinstance(item, (WODDice, DXDice, BonusPunishDice, Dice, FudgeDice)):  # 检查骰子类型并投掷
                item.Roll(msg)
                res = item.GetResult()
                if times * dice_count < MAX_DETAIL_CNT:
                    dice_detail_list[i] = f'({item.GetDetail()})'
                else:
                    dice_detail_list[i] = f'({str(res)})' if res < 0 else str(res)  # 负数加括号
                dice_res_list[i] = f'({str(res)})' if res < 0 else str(res)
            else:
                continue
        dice_detail_list = insert_multiply(dice_detail_list, use_markdown)
        dice_res_list = insert_multiply(dice_res_list)
        output_line += ''.join(dice_detail_list)
        Logger.debug(dice_detail_list)
        Logger.debug(dice_res_list)
        try:
            if dice_res_list:
                dice_res = ''.join(dice_res_list)
                dice_res = dice_res.replace('\\*', '*')
                Logger.debug(dice_res)
                result = int(se.eval(dice_res))
            else:
                raise SyntaxError
        except (FunctionNotDefined, NameNotDefined, SyntaxError, TypeError):
            return DiceSyntaxError(msg, msg.locale.t('dice.message.error.syntax')).message
        except Exception as e:
            return DiceValueError(msg, msg.locale.t('dice.message.error') + '\n' + str(e)).message
        output_line += '=' + str(result)

        if dc:
            output_line += f'/{dc}  '
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
