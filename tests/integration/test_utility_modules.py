"""工具模块集成测试 - dice, coin, random 等。"""

from core.tester import (
    func_case,
    Tester,
    Regex,
    Contains,
    Predicate,
)


@func_case
async def test_random(tester: Tester):
    """random 模块测试"""

    def is_number(result):
        output = result.get("output")
        if not output:
            return False
        for item in output:
            item_str = str(item).strip()
            if item_str.isdigit():
                return True
        return False

    def is_choice(result):
        output = result.get("output")
        if not output:
            return False
        choices = ["apple", "banana", "cherry"]
        for item in output:
            item_str = str(item).strip().lower()
            if item_str in choices:
                return True
        return False

    await tester.integrate("~random number 1 100", Predicate(is_number), "random number 应输出数字")
    await tester.integrate("~random choice apple banana cherry", Predicate(is_choice), "random choice 应输出选项之一")
    await tester.integrate(
        "~random uuid",
        Regex(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
        "random uuid 应为合法 UUID 格式",
    )

    return tester


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
