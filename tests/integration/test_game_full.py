"""游戏模块完整流程集成测试。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_chemical_code_full(tester: Tester):
    """chemical_code 完整流程测试"""
    await tester.integrate("~chemical_code stop", Contains("游戏"), "chemical_code stop 应提示游戏状态")
    return tester


@func_case
async def test_wordle_full(tester: Tester):
    """wordle 完整流程测试"""
    await tester.integrate(
        ["~wordle", "crane", "audio", "light", "moist", "plant", "blame"], Contains("游戏"), "wordle 完整游戏流程"
    )
    return tester


@func_case
async def test_twenty_four_full(tester: Tester):
    """twenty_four 完整流程测试"""
    await tester.integrate(["~twenty_four", "1+2+3+4"], Contains("数字"), "twenty_four 应显示数字组合")
    return tester
