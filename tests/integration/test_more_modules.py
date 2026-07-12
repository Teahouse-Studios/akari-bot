"""更多模块集成测试 - convert、color 等。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_convert(tester: Tester):
    """convert 模块测试 - 单位转换"""
    await tester.integrate("~convert 100km mi", Contains("mi"), "convert 应输出目标单位")
    return tester


@func_case
async def test_color(tester: Tester):
    """color 模块测试 - 颜色查询"""
    await tester.integrate("~color #FF0000", Contains("HEX"), "color 应输出 HEX 值")
    await tester.integrate("~color #FF0000", Contains("RGB"), "color 应输出 RGB 值")
    return tester
