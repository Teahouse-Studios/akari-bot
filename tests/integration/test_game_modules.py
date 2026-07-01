"""游戏模块集成测试 - wordle, twenty_four, chemical_code 等。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_wordle(tester: Tester):
    """wordle 模块测试 - Wordle 游戏完整流程"""
    await tester.expect(
        ["~wordle", "crane", "audio", "light", "moist", "plant", "blame"], Contains("游戏"), "wordle 完整游戏流程"
    )
    return tester


@func_case
async def test_wordle_stop(tester: Tester):
    """wordle stop 测试 - 停止未开始的游戏"""
    await tester.expect("~wordle stop", Contains("游戏"), "wordle stop 应提示游戏状态")
    return tester


@func_case
async def test_twenty_four(tester: Tester):
    """twenty_four 模块测试 - 24点游戏"""
    await tester.expect(["~twenty_four", "1+2+3+4"], Contains("数字"), "twenty_four 应显示数字组合")
    return tester


@func_case
async def test_twenty_four_no_solution(tester: Tester):
    """twenty_four 无解测试"""
    await tester.expect(["~twenty_four", "无解"], Contains("回答"), "twenty_four 无解应有回答反馈")
    return tester


@func_case
async def test_twenty_four_stop(tester: Tester):
    """twenty_four stop 测试 - 停止未开始的游戏"""
    await tester.expect("~twenty_four stop", Contains("游戏"), "twenty_four stop 应提示游戏状态")
    return tester


@func_case
async def test_chemical_code_stop(tester: Tester):
    """chemical_code stop 测试 - 停止未开始的游戏"""
    await tester.expect("~chemical_code stop", Contains("游戏"), "chemical_code stop 应提示游戏状态")
    return tester
