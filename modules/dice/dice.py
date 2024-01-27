import re
import secrets

import numpy as np

from config import Config
from core.exceptions import ConfigValueError
from core.utils.text import remove_prefix

MAX_DICE_COUNT = Config('dice_limit', 100)  # 一次摇动最多的骰子数量
MAX_ROLL_TIMES = Config('dice_roll_limit', 10)  # 一次命令最多的摇动次数
MAX_MOD_NUMBER = Config('dice_mod_max', 10000)  # 骰子最大加权值
MIN_MOD_NUMBER = Config('dice_mod_min', -10000)  # 骰子最小加权值
MAX_OUTPUT_CNT = Config('dice_output_count', 50)  # 输出的最多数据量
MAX_OUTPUT_LEN = Config('dice_output_len', 200)  # 输出的最大长度
MAX_DETAIL_CNT = Config('dice_detail_count', 5)  # n次投掷的骰子的总量超过该值时将不再显示详细信息
MAX_ITEM_COUNT = Config('dice_count_limit', 10)  # 骰子多项式最多的项数


class DiceSyntaxError(Exception):
    """骰子语法错误"""

    def __init__(self, msg, message):
        self.message = msg.locale.t("dice.message.error.syntax") + message


class DiceValueError(Exception):
    """骰子参数值错误"""

    def __init__(self, msg, message, value=None):
        if value:
            self.message = msg.locale.t("dice.message.error.value.invalid", value=value) + message
        else:
            self.message = msg.locale.t("dice.message.error.value") + message


class DiceItemBase(object):
    """骰子项的基类"""

    def __init__(self, dice_code: str, positive: bool):
        self.positive = positive
        self.code = dice_code
        self.result = None
        self.detail = ''

    def GetResult(self, abs=True):
        if abs:
            return self.result
        else:
            return self.result if self.positive else -self.result

    def GetDetail(self):
        return self.detail

    def Roll(self, msg, use_markdown: bool=False):
        pass


class DiceMod(DiceItemBase):
    """调节值项"""

    def __init__(self, msg, dice_code: str, positive: bool):
        super().__init__(dice_code, positive)
        if not dice_code.isdigit():
            raise DiceValueError(msg,
                                 msg.locale.t("dice.message.error.value.M.invalid"),
                                 '+' if self.positive else '-' + dice_code)
        else:
            self.result = int(dice_code)
            if self.result > MAX_MOD_NUMBER or self.result < MIN_MOD_NUMBER:
                raise DiceValueError(msg,
                                     msg.locale.t("dice.message.error.value.M.out_of_range", min=MIN_MOD_NUMBER,
                                                      max=MAX_MOD_NUMBER),
                                     self.result)

    def GetDetail(self):
        return self.result


class Dice(DiceItemBase):
    """骰子项"""

    def __init__(self, msg, dice_code: str, positive: bool):

        dice_code = dice_code.replace(' ', '')
        super().__init__(dice_code, positive)
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
                                 msg.locale.t("dice.message.error.value.n.less2"),
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
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.syntax.invalid"))
        if 'D' not in dice_code:
            raise DiceSyntaxError(msg, msg.locale.t("dice.message.error.syntax.missing_d"))
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
        if msg.target.sender_from in ['Discord|Client', 'Kook|User', 'Telegram|User']:
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
                        output_buffer += f"**{str(dice_results[i])}**"
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
            output += output_buffer + ') = '
            dice_results = new_results
        # 公用加法
        length = len(dice_results)
        if (length > 1):
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


async def GenerateMessage(msg, dices: str, times: int, dc: int):
    if not all([MAX_DICE_COUNT > 0, MAX_ROLL_TIMES > 0, MAX_MOD_NUMBER >= MIN_MOD_NUMBER, MAX_OUTPUT_CNT > 0,
                MAX_OUTPUT_LEN > 0, MAX_DETAIL_CNT > 0, MAX_ITEM_COUNT > 0]):
        raise ConfigValueError(msg.locale.t("error.config.invalid"))
    if re.search(r'[^0-9+\-DKL]', dices.upper()):
        return DiceSyntaxError(msg, msg.locale.t('dice.message.error.syntax.invalid')).message
    if times > MAX_ROLL_TIMES or times < 1:
        return DiceValueError(msg, msg.locale.t('dice.message.error.value.N.out_of_range', max=MAX_ROLL_TIMES),
                              times).message
    dice_code_cist = re.compile(r'[+-]?[^+-]+').findall(dices)
    dice_list = []
    have_err = False
    output = ""
    dice_count = 0
    i = 0
    if len(dice_code_cist) > MAX_ITEM_COUNT:
        return DiceValueError(msg, msg.locale.t('dice.message.error.value.too_long'), len(dice_code_cist)).message
    # 初始化骰子序列
    for item in dice_code_cist:
        i += 1
        is_add = True
        if item[0] == '-':
            is_add = False
            item = item[1:]
        if item[0] == '+':
            item = item[1:]
        try:
            if 'D' in item or 'd' in item:
                d = Dice(msg, item, is_add)
                dice_list.append(d)
                dice_count += d.count
            elif item.isdigit():
                dice_list.append(DiceMod(msg, item, is_add))
        except (DiceSyntaxError, DiceValueError) as ex:
            output += '\n' + msg.locale.t('dice.message.error.prompt', i=i) + ex.message
            have_err = True
    if have_err:
        return msg.locale.t('dice.message.error') + output
    success_num = 0
    fail_num = 0
    output = msg.locale.t('dice.message.output')
    # 开始投掷并输出
    for i in range(times):
        output_line = ''
        result = 0
        for dice in dice_list:
            dice.Roll(msg)
            output_line += '+' if dice.positive else '-'
            if isinstance(dice, Dice) and times * dice_count < MAX_DETAIL_CNT:
                output_line += f'({dice.GetDetail()})'
            else:
                output_line += str(dice.GetResult())
            result += dice.GetResult(False)
        output_line = remove_prefix(output_line, '+')  # 移除多项式首个+
        output_line += ' = ' + str(result)
        if dc != 0:
            if msg.data.options.get('dice_dc_reversed'):
                if result <= dc:
                    output_line += msg.locale.t('dice.message.dc.success')
                    success_num += 1
                else:
                    output_line += msg.locale.t('dice.message.dc.failed')
                    fail_num += 1
            else:
                if result >= dc:
                    output_line += msg.locale.t('dice.message.dc.success')
                    success_num += 1
                else:
                    output_line += msg.locale.t('dice.message.dc.failed')
                    fail_num += 1
        output += f'\n{dices} = {output_line}'
    if dc != 0 and times > 1:
        output += '\n' + msg.locale.t('dice.message.dc.check', success=str(success_num), failed=str(fail_num))
    return output
