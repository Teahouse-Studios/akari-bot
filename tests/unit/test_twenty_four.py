"""twenty_four 求解器单元测试 - 表达式枚举与结果校验。

模块的集成测试只断言输出含有特定文本，求解器给出的表达式是否真的等于 24、
是否恰好用尽给定的四个数，均不在其覆盖范围内，故在此直接求证。

命令函数传给 find_solution 的是元组，求解器内部又以下标取值，元组入参因而是
必须守住的一条路径：曾有一次改写将下标循环误写为 enumerate，正是在这条路径上
抛出 TypeError。
"""

from core.tester import func_case, Tester
from modules.twenty_four import calc, check_valid, contains_all_numbers, find_solution

# 需借助除法与括号才能凑成 24 的经典组合，用于检验求解器不止会做整数四则运算。
TRICKY_NUMBERS = (3, 3, 8, 8)
# 四个 1 至多凑出 4，必定无解。
NO_SOLUTION_NUMBERS = (1, 1, 1, 1)


def _all_solutions_valid(numbers) -> bool:
    """求证每个解均语法合法、求值为 24 且恰好用尽给定的数。"""
    solutions = find_solution(numbers)
    if not solutions:
        return False
    for expr in solutions:
        if not check_valid(expr):
            return False
        result = calc(expr)
        if result is None or abs(result - 24) >= 1e-10:
            return False
        if not contains_all_numbers(expr, numbers):
            return False
    return True


async def _test_accepts_tuple():
    """测试求解 - 接受元组入参，即命令函数实际传入的类型"""
    try:
        return _all_solutions_valid((1, 2, 3, 4))

    except Exception:
        return False


async def _test_accepts_list():
    """测试求解 - 接受列表入参"""
    try:
        return _all_solutions_valid([1, 2, 3, 4])

    except Exception:
        return False


async def _test_solves_with_division():
    """测试求解 - 解出需借助除法与括号的组合"""
    try:
        return _all_solutions_valid(TRICKY_NUMBERS)

    except Exception:
        return False


async def _test_no_solution_returns_none():
    """测试求解 - 无解的组合返回 None"""
    try:
        return find_solution(NO_SOLUTION_NUMBERS) is None

    except Exception:
        return False


@func_case
async def test_twenty_four_solver(tester: Tester):
    """twenty_four 求解器：入参类型、解的正确性与无解判定测试"""
    await tester.test(_test_accepts_tuple, "元组入参测试")
    await tester.test(_test_accepts_list, "列表入参测试")
    await tester.test(_test_solves_with_division, "含除法组合求解测试")
    await tester.test(_test_no_solution_returns_none, "无解返回 None 测试")

    return tester
