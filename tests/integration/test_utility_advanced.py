"""工具模块高级集成测试 - dice 复杂表达式。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_dice_complex(tester: Tester):
    """dice 复杂表达式测试

    dice 模块以 K 表示保留高位、Q 表示保留低位，不支持 kh/kl 写法。
    """
    await tester.integrate("~dice 4d6k3", Contains("掷得"), "dice 4d6k3 应输出保留高位结果")
    await tester.integrate("~dice 4d6q3", Contains("掷得"), "dice 4d6q3 应输出保留低位结果")
    await tester.integrate("~dice 2d6+3", Contains("掷得"), "dice 2d6+3 应输出结果")
    return tester


@func_case
async def test_dice_d20(tester: Tester):
    """dice d20 测试"""
    await tester.integrate("~dice d20", Contains("d20"), "dice d20 应包含表达式")
    await tester.integrate("~dice d20 10", Contains("掷得"), "dice d20 10 应输出判定结果")
    return tester


@func_case
async def test_dice_invalid(tester: Tester):
    """dice 无效表达式测试"""
    await tester.integrate("~dice invalid_xyz", Contains("骰子"), "dice 无效表达式应提示错误")
    await tester.integrate("~dice 4d6kh3", Contains("无效的骰子表达式"), "dice 不支持的 kh 写法应报错")
    return tester
