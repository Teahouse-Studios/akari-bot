"""游戏模块完整流程集成测试。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_chemical_code_full(tester: Tester):
    """chemical_code 完整流程测试"""
    await tester.integrate("~chemical-code stop", Contains("游戏"), "chemical-code stop 应提示游戏状态")
    return tester


@func_case
async def test_twenty_four_full(tester: Tester):
    """twenty_four 完整流程测试"""
    await tester.integrate(["~twenty-four", "1+2+3+4"], Contains("数字"), "twenty-four 应显示数字组合")
    return tester
