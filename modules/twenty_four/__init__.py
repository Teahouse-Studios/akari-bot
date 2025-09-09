import itertools

from simpleeval import simple_eval

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.utils.game import PlayState, GAME_EXPIRED
from core.utils.message import isint
from core.utils.petal import gained_petal, lost_petal
from core.utils.random import Random

no_solution_lst = [
    "无解",
    "無解",
    "none",
    "n/a",
    "na",
    "n.a.",
]


def calc(expr):
    expr = expr.replace("\\", "")
    try:
        return simple_eval(expr)
    except Exception:
        return None


def check_valid(expr):
    expr = expr.replace(" ", "")

    operators = {"+", "-", "*", "/"}
    num_numbers = 0
    open_parens = 0
    prev_char = ""

    i = 0
    while i < len(expr):
        char = expr[i]
        if isint(char):
            while i < len(expr) and isint(expr[i]):
                i += 1
            num_numbers += 1
            prev_char = "num"
            continue
        if char in operators:
            if prev_char in operators or prev_char in ("", "("):
                return False
            prev_char = char
            i += 1
        if char == "(":
            if prev_char in ("num", ")"):
                return False
            open_parens += 1
            prev_char = char
            i += 1
        if char == ")":
            if open_parens <= 0 or prev_char in operators or prev_char in ("", "("):
                return False
            open_parens -= 1
            prev_char = char
            i += 1
        if char == "\\":
            i += 1
            continue
        return False

    if open_parens != 0:
        return False
    if num_numbers > 9:
        return False
    if prev_char in operators:
        return False

    return True


async def find_solution(numbers):
    perms = list(itertools.permutations(numbers))
    operators = ["+", "-", "*", "/"]
    exprs = list(itertools.product(operators, repeat=4))

    for perm in perms:
        for expr in exprs:  # 穷举就完事了
            exp = f"(({perm[0]}{expr[0]}{perm[1]}){expr[1]}{perm[2]}){expr[2]}{perm[3]}"
            try:
                if calc(exp) == 24 or 0 < 24 - calc(exp) < 1e-13:
                    return exp
            except Exception:
                pass
            exp = f"({perm[0]}{expr[0]}{perm[1]}){expr[1]}({perm[2]}{expr[2]}{perm[3]})"
            try:
                if calc(exp) == 24 or 0 < 24 - calc(exp) < 1e-13:
                    return exp
            except Exception:
                pass
            exp = f"{perm[0]}{expr[0]}({perm[1]}{expr[1]}({perm[2]}{expr[2]}{perm[3]}))"
            try:
                if calc(exp) == 24 or 0 < 24 - calc(exp) < 1e-13:
                    return exp
            except Exception:
                pass
            exp = f"{perm[0]}{expr[0]}({perm[1]}{expr[1]}{perm[2]}){expr[2]}{perm[3]}"
            try:
                if calc(exp) == 24 or 0 < 24 - calc(exp) < 1e-13:
                    return exp
            except Exception:
                pass
    return None


def contains_all_numbers(expr, numbers):
    used_numbers = [str(num) for num in numbers]
    used_count = {str(num): 0 for num in numbers}
    i = 0
    while i < len(expr):
        char = expr[i]
        if isint(char):
            number = char
            while i + 1 < len(expr) and isint(expr[i + 1]):
                number += expr[i + 1]
                i += 1
            if number in used_numbers:
                used_count[number] += 1
                if used_count[number] > numbers.count(int(number)):
                    return False
            else:
                return False
        i += 1

    return bool(all(used_count[str(num)] == numbers.count(num) for num in numbers))


tf = module(
    "twenty_four",
    alias=["twentyfour", "24"],
    desc="{I18N:twenty_four.help.desc}",
    developers=["DoroWolf"],
    doc=True,
)


@tf.command("{{I18N:twenty_four.help}}")
async def _(msg: Bot.MessageSession):
    play_state = PlayState("twenty_four", msg)
    if play_state.check():
        await msg.finish(I18NContext("game.message.running"))
    else:
        play_state.enable()

    numbers = [Random.randint(1, 13) for _ in range(4)]
    solution = await find_solution(numbers)

    answer = await msg.wait_next_message(I18NContext("twenty_four.message", numbers=numbers), timeout=GAME_EXPIRED)
    expr = answer.as_display(text_only=True)
    if play_state.check():
        play_state.disable()
        if expr.lower() in no_solution_lst:
            if solution:
                if msg.session_info.support_markdown:
                    solution.replace("*", "\\*")
                send = [I18NContext("twenty_four.message.incorrect.have_solution", solution=solution)]
                if g_msg := (g_msg := await lost_petal(msg, 1)):
                    send.append(g_msg)
            else:
                send = [I18NContext("twenty_four.message.correct")]
                if g_msg := await gained_petal(msg, 1):
                    send.append(g_msg)
            await answer.finish(send)
        elif check_valid(expr):
            result = calc(expr)
            if not result:
                await answer.finish(I18NContext("twenty_four.message.incorrect.invalid"))
            elif (result == 24 or 0 < 24 - result < 1e-13) and \
                    contains_all_numbers(expr, numbers):
                send = [I18NContext("twenty_four.message.correct")]
                if g_msg := await gained_petal(msg, 1):
                    send.append(g_msg)
                await answer.finish(send)
            else:
                await answer.finish(I18NContext("twenty_four.message.incorrect"))
        else:
            await answer.finish(I18NContext("twenty_four.message.incorrect.invalid"))


@tf.command("stop {{I18N:game.help.stop}}")
async def s(msg: Bot.MessageSession):
    play_state = PlayState("twenty_four", msg)
    if play_state.check():
        play_state.disable()
        await msg.finish(I18NContext("game.message.stop"))
    else:
        await msg.finish(I18NContext("game.message.stop.none"))
