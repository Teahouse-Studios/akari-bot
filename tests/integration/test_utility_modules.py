"""工具模块集成测试 - dice, coin 等。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_dice(tester: Tester):
    """dice 模块测试"""
    await tester.integrate("~dice", Contains("无法解析"), "dice 默认应提示无法解析")
    await tester.integrate("~dice 2d6", Contains("掷得"), "dice 2d6 应输出掷骰子结果")
    await tester.integrate("~dice 2d6", Contains("2d6"), "dice 2d6 应包含表达式")
    await tester.integrate("~dice d20", Contains("掷得"), "dice d20 应输出掷骰子结果")
    await tester.integrate("~dice d20", Contains("d20"), "dice d20 应包含表达式")
    await tester.integrate("~dice d20 10", Contains("掷得"), "dice d20 10 应输出掷骰子结果")

    return tester


@func_case
async def test_coin(tester: Tester):
    """coin 模块测试"""
    await tester.integrate("~coin", Contains("硬币"), "coin 应输出硬币结果")
    await tester.integrate("~coin 10", Contains("硬币"), "coin 10 应输出多枚硬币结果")
    await tester.integrate("~coin 10", Contains("10"), "coin 10 应包含数量")
    await tester.integrate("~coin 0", Contains("空气"), "coin 0 应提示空气")
    await tester.integrate("~coin -1", Contains("无效"), "coin -1 应提示无效数量")

    return tester


@func_case
async def test_hitokoto(tester: Tester):
    """hitokoto 模块测试"""
    await tester.integrate("~hitokoto", Contains("hitokoto.cn"), "hitokoto 应包含来源链接")

    return tester


@func_case
async def test_langconv(tester: Tester):
    """langconv 模块测试"""
    await tester.integrate("~langconv zh-cn 你好", Contains("你好"), "langconv 应输出转换结果")

    return tester
