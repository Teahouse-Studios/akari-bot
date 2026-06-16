from simpleeval import simple_eval

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.game import PlayState, GAME_EXPIRED
from core.utils.petal import cost_petal, gained_petal, lost_petal
from core.utils.random import Random
from core.utils.func import is_int

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
    num_counts = 0
    open_parens = 0
    prev_char = ""

    i = 0
    while i < len(expr):
        char = expr[i]
        if is_int(char):
            while i < len(expr) and is_int(expr[i]):
                i += 1
            num_counts += 1
            prev_char = "X"
            continue
        if char in operators:
            if char == "-" and prev_char in ("", "("):
                prev_char = "~"
                i += 1
                continue
            if prev_char in operators or prev_char in ("", "(", "~"):
                return False
            prev_char = char
            i += 1
            continue
        if char == "(":
            if prev_char in ("X", ")"):
                return False
            open_parens += 1
            prev_char = char
            i += 1
            continue
        if char == ")":
            if open_parens <= 0 or prev_char in operators or prev_char in ("", "("):
                return False
            open_parens -= 1
            prev_char = char
            i += 1
            continue
        if char == "\\":  # expr may have additional escape chars
            i += 1
            continue
        return False

    if open_parens != 0:
        return False
    if prev_char in operators:
        return False

    return True


def contains_all_numbers(expr, numbers):
    used_numbers = [str(num) for num in numbers]
    used_count = {str(num): 0 for num in numbers}
    i = 0
    while i < len(expr):
        char = expr[i]
        if is_int(char):
            number = char
            while i + 1 < len(expr) and is_int(expr[i + 1]):
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


def find_solution(numbers):
    ops = {
        "+": (lambda a, b: a + b, 1),
        "-": (lambda a, b: a - b, 1),
        "*": (lambda a, b: a * b, 2),
        "/": (lambda a, b: a / b if b != 0 else None, 2),
    }

    results = set()

    def dfs(nums, exprs):
        if len(nums) == 1:
            if nums[0] is not None and abs(nums[0] - 24) < 1e-10:
                results.add(exprs[0][0])
            return

        for i in range(len(nums)):
            for j in range(len(nums)):
                if i == j:
                    continue

                a, b = nums[i], nums[j]
                expr_a, prec_a = exprs[i]
                expr_b, prec_b = exprs[j]

                rest_nums = [nums[k] for k in range(len(nums)) if k != i and k != j]
                rest_exprs = [exprs[k] for k in range(len(nums)) if k != i and k != j]

                for op, (func, prec) in ops.items():
                    if op in ["+", "*"] and j < i:
                        continue

                    val = func(a, b)
                    if val is None:
                        continue

                    left = expr_a
                    if prec_a < prec:
                        left = f"({left})"

                    right = expr_b
                    if prec_b < prec or (op in ["-", "/"] and prec_b == prec):
                        right = f"({right})"

                    new_expr = f"{left}{op}{right}"

                    dfs(rest_nums + [val], rest_exprs + [(new_expr, prec)])

    dfs(numbers, [(str(x), 3) for x in numbers])

    return list(results) if results else None


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

    play_state.enable()
    numbers = tuple(Random.randint(1, 13) for _ in range(4))
    play_state.update(numbers=numbers)
    solution = find_solution(numbers)

    answer = await msg.wait_next_message(I18NContext("twenty_four.message", numbers=numbers), timeout=GAME_EXPIRED)
    expr = answer.as_display(text_only=True)
    if play_state.check():
        play_state.disable()
        if expr.lower() in no_solution_lst:
            if solution:
                solution = solution[0]
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
        if check_valid(expr):
            result = calc(expr)
            if not result:
                await answer.finish(I18NContext("twenty_four.message.incorrect.invalid"))
            elif (result == 24 or 0 < 24 - result < 1e-13) and contains_all_numbers(expr, numbers):
                send = [I18NContext("twenty_four.message.correct")]
                if g_msg := await gained_petal(msg, 1):
                    send.append(g_msg)
                await answer.finish(send)
            await answer.finish(I18NContext("twenty_four.message.incorrect"))
        await answer.finish(I18NContext("twenty_four.message.incorrect.invalid"))


@tf.command("stop {{I18N:game.help.stop}}")
async def _(msg: Bot.MessageSession):
    play_state = PlayState("twenty_four", msg)
    if play_state.check():
        play_state.disable()
        await msg.finish(I18NContext("game.message.stop"))
    await msg.finish(I18NContext("game.message.stop.none"))


@tf.command("solve <num1> <num2> <num3> <num4> {{I18N:twenty_four.help.solve}}")
async def _(msg: Bot.MessageSession, num1: int, num2: int, num3: int, num4: int):
    numbers = (num1, num2, num3, num4)
    play_state = PlayState("twenty_four", msg)
    if play_state.check():
        await msg.finish(I18NContext("twenty_four.message.solve.running"))
    if not all(1 <= x <= 13 for x in numbers):
        await msg.finish(I18NContext("twenty_four.message.solve.invalid"))
    if not (msg.check_super_user() or await cost_petal(msg, 4)):
        await msg.finish()

    solutions = find_solution(numbers)
    if solutions:
        msg_chain = [I18NContext("twenty_four.message.solve.prompt", numbers=numbers)]
        for solution in solutions:
            if msg.session_info.support_markdown:
                solution.replace("*", "\\*")
            msg_chain.append(Plain(solution))
    else:
        msg_chain = [I18NContext("twenty_four.message.solve.no_solution", numbers=numbers)]

    await msg.finish(msg_chain)
