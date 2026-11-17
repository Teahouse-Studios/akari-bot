import math

from simpleeval import SimpleEval, FunctionNotDefined, NameNotDefined

from core.builtins.bot import Bot
from core.builtins.message.internal import Plain
from core.constants.exceptions import ConfigValueError
from core.logger import Logger
from .dice import *
from modules.dice.config import DiceConfig

MAX_DICE_COUNT = DiceConfig.dice_limit
MAX_ROLL_TIMES = DiceConfig.dice_roll_limit
MAX_OUTPUT_CNT = DiceConfig.dice_output_count
MAX_OUTPUT_LEN = DiceConfig.dice_output_len
MAX_DETAIL_CNT = DiceConfig.dice_detail_count  # n次投掷的骰子的总量超过该值时将不再显示详细信息
MAX_ITEM_COUNT = DiceConfig.dice_count_limit

dice_patterns = [
    r"(\d+A\d+(?:[KQM]?\d*)?(?:[KQM]?\d*)?(?:[KQM]?\d*)?)",
    r"(\d+C\d+M?\d*)",
    r"(?:D(?:100|%)?)?([BP]\d*)",
    r"(\d*D?F)",
    r"(\d*D\d*%?(?:K\d*|Q\d*)?)",
    r"(\d+)",
    r"([\(\)])",
]

math_funcs = {
    "abs": abs,
    "ceil": math.ceil,
    "comb": math.comb,
    "exp": math.exp,
    "fabs": math.fabs,
    "factorial": math.factorial,
    "fmod": math.fmod,
    "floor": math.floor,
    "gcd": math.gcd,
    "lcm": math.lcm,
    "log": math.log,
    "perm": math.perm,
    "pow": math.pow,
    "sqrt": math.sqrt,
}

se = SimpleEval()
se.functions.update(math_funcs)


async def process_expression(msg: Bot.MessageSession, expr: str, dc: int | None):
    if not all(
        [
            MAX_DICE_COUNT > 0,
            MAX_ROLL_TIMES > 0,
            MAX_OUTPUT_CNT > 0,
            MAX_OUTPUT_LEN > 0,
            MAX_DETAIL_CNT > 0,
            MAX_ITEM_COUNT > 0,
        ]
    ):
        raise ConfigValueError("{I18N:error.config.invalid}")
    if msg.session_info.support_markdown:
        expr = expr.replace("*", "\\*")

    dice_list, count, times, err = parse_dice_expression(msg, expr)
    if err:
        return err
    output = generate_dice_message(msg, expr, dice_list, count, times, dc)
    return output


def parse_dice_expression(msg: Bot.MessageSession, dices: str):
    dice_item_list = []
    math_func_pattern = "(" + "|".join(re.escape(func) for func in math_funcs) + ")"
    errmsg = None

    dices = re.sub(r"(\d+)\.\d+", r"\1", dices)
    if "#" in dices:
        times = dices.partition("#")[0]
        dices = dices.partition("#")[2]
    else:
        times = "1"
    if not is_int(times):
        errmsg = "{I18N:dice.message.error.value.times.invalid}"
        return (
            None,
            None,
            None,
            DiceValueError("{I18N:dice.message.error}" + "\n" + errmsg).message,
        )

    dice_expr_list = re.split(f"{math_func_pattern}|" + "|".join(dice_patterns), dices, flags=re.I)
    dice_expr_list = [item for item in dice_expr_list if item]
    for item in range(len(dice_expr_list)):
        if (
            dice_expr_list[item][-1].upper() == "D"
            and dice_expr_list[item] not in math_funcs
            and msg.session_info.target_union_info.target_data.get("dice_default_sides")
        ):
            dice_expr_list[item] += str(msg.session_info.target_union_info.target_data.get("dice_default_sides"))

    for i, item in enumerate(dice_expr_list):
        for pattern in dice_patterns:
            match = re.match(pattern, item, flags=re.I)
            if match:
                dice_expr_list[i] = item.upper()
                dice_item_list.append(item)
                break
        func_match = re.match(math_func_pattern, item, flags=re.I)
        if func_match:
            dice_expr_list[i] = item.lower()

    Logger.debug(dice_expr_list)
    if len(dice_item_list) > MAX_ITEM_COUNT:
        errmsg = "{I18N:dice.message.error.value.too_long}"
        return (
            None,
            None,
            None,
            DiceValueError("{I18N:dice.message.error}" + errmsg).message,
        )

    dice_count = 0
    for j, item in enumerate(dice_expr_list):
        try:
            if any(item.lower() == func for func in math_funcs):
                continue
            if "A" in item:
                dice_count += 1
                dice_expr_list[j] = WODDice(item)
            elif "C" in item:
                dice_count += 1
                dice_expr_list[j] = DXDice(item)
            elif "B" in item or "P" in item:
                dice_count += 1
                dice_expr_list[j] = BonusPunishDice(item)
            elif "F" in item:
                dice_count += 1
                dice_expr_list[j] = FudgeDice(item)
            elif "D" in item:
                dice_count += 1
                dice_expr_list[j] = Dice(item)
            elif is_int(item):
                dice_count += 1
            else:
                continue
        except (DiceSyntaxError, DiceValueError) as ex:
            errmsg = str(I18NContext("dice.message.error.prompt", i=dice_count)) + ex.message
    if errmsg:
        return (
            None,
            None,
            None,
            DiceValueError("{I18N:dice.message.error}" + "\n" + errmsg).message,
        )
    return dice_expr_list, dice_count, int(times), None


def insert_multiply(msg: Bot.MessageSession, lst: list):
    result = []
    asterisk = "\\*" if msg.session_info.support_markdown else "*"
    for i, item in enumerate(lst):
        if i == 0:
            result.append(item)
        else:
            if is_int(lst[i - 1][-1]) and is_int(item[0]):
                result.append(asterisk)
            elif lst[i - 1][-1] == ")" and item[0] == "(":
                result.append(asterisk)
            elif is_int(lst[i - 1][-1]) and item[0] == "(":
                result.append(asterisk)
            elif lst[i - 1][-1] == ")" and is_int(item[0]):
                result.append(asterisk)
            result.append(item)
    return result


def generate_dice_message(
    msg: Bot.MessageSession,
    expr: str,
    dice_expr_list: list,
    dice_count: int,
    times: int,
    dc: int | None,
):
    success_num = 0
    fail_num = 0
    output = [I18NContext("dice.message.output")]
    if "#" in expr:
        expr = expr.partition("#")[2]
    if times < 1 or times > MAX_ROLL_TIMES:
        errmsg = str(I18NContext("dice.message.error.value.times.out_of_range", max=MAX_ROLL_TIMES))
        return DiceValueError("{I18N:dice.message.error}" + "\n" + errmsg).message

    for _ in range(times):
        dice_detail_list = dice_expr_list.copy()
        dice_res_list = dice_expr_list.copy()
        output_line = ""
        for i, item in enumerate(dice_detail_list):
            if isinstance(item, (WODDice, DXDice, BonusPunishDice, Dice, FudgeDice)):
                item.roll()
                res = item.get_result()
                if times * dice_count < MAX_DETAIL_CNT:
                    dice_detail_list[i] = f"({item.get_detail()})"
                else:
                    dice_detail_list[i] = f"({res})" if res < 0 else str(res)
                dice_res_list[i] = f"({res})" if res < 0 else str(res)
            else:
                continue
        dice_detail_list = insert_multiply(msg, dice_detail_list)
        dice_res_list = insert_multiply(msg, dice_res_list)
        output_line += "".join(dice_detail_list)
        try:
            if dice_res_list:
                dice_res = "".join(dice_res_list)
                dice_res = dice_res.replace("\\*", "*")
                Logger.debug(dice_res)
                result = int(se.eval(dice_res))
            else:
                raise SyntaxError
        except (FunctionNotDefined, NameNotDefined, SyntaxError, TypeError):
            return DiceSyntaxError("{I18N:dice.message.error.syntax}").message
        except Exception as e:
            return DiceValueError("{I18N:dice.message.error}" + "\n" + str(e)).message
        try:
            output_line += f"={fmt_num(result, sep=True)}"
        except Exception:
            return DiceValueError("{I18N:dice.message.error}" + "\n" + "{I18N:dice.message.too_long}").message

        try:
            if dc:
                output_line += f"/{dc}  "
                if msg.session_info.target_union_info.target_data.get("dice_dc_reversed"):
                    if int(result) <= dc:
                        output_line += "{I18N:dice.message.dc.success}"
                        success_num += 1
                    else:
                        output_line += "{I18N:dice.message.dc.fail}"
                        fail_num += 1
                else:
                    if int(result) >= dc:
                        output_line += "{I18N:dice.message.dc.success}"
                        success_num += 1
                    else:
                        output_line += "{I18N:dice.message.dc.fail}"
                        fail_num += 1
            output.append(Plain(f"{expr}={output_line}"))
        except ValueError:
            return "{I18N:dice.message.dc.invalid}" + str(dc)
    if dc and times > 1:
        output.append(I18NContext("dice.message.dc.check", success=success_num, failed=fail_num))
    return output
