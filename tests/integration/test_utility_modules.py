"""工具模块集成测试 - dice, coin, convert, color, nbnhhsh, idlist 等。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
    ContainsAll,
)


@func_case
async def test_dice(tester: Tester):
    """dice 模块测试"""
    await tester.integrate("~dice", Contains("无法解析"), "dice 默认应提示无法解析")
    await tester.integrate("~dice 2d6", ContainsAll("掷得", "2d6"), "dice 2d6 应输出表达式与掷骰子结果")
    await tester.integrate("~dice d20", ContainsAll("掷得", "d20"), "dice d20 应输出表达式与掷骰子结果")
    await tester.integrate("~dice d20 10", Contains("掷得"), "dice d20 10 应输出掷骰子结果")
    await tester.integrate("~dice 4d6k3", Contains("掷得"), "dice 4d6k3 应输出保留高位结果")
    await tester.integrate("~dice 4d6q3", Contains("掷得"), "dice 4d6q3 应输出保留低位结果")
    await tester.integrate("~dice 2d6+3", Contains("掷得"), "dice 2d6+3 应输出结果")
    await tester.integrate("~dice invalid_xyz", Contains("骰子"), "dice 无效表达式应提示错误")
    await tester.integrate("~dice 4d6kh3", Contains("无效的骰子表达式"), "dice 不支持的 kh 写法应报错")

    return tester


@func_case
async def test_coin(tester: Tester):
    """coin 模块测试"""
    await tester.integrate("~coin", Contains("硬币"), "coin 应输出硬币结果")
    await tester.integrate("~coin 10", ContainsAll("硬币", "10"), "coin 10 应输出多枚硬币结果与数量")
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


@func_case
async def test_convert(tester: Tester):
    """convert 模块测试 - 单位转换"""
    await tester.integrate("~convert 100km mi", Contains("mi"), "convert 应输出目标单位")

    return tester


@func_case
async def test_color(tester: Tester):
    """color 模块测试 - 颜色查询"""
    await tester.integrate("~color #FF0000", ContainsAll("HEX", "RGB"), "color 应输出 HEX 与 RGB 值")

    return tester


@func_case
async def test_nbnhhsh(tester: Tester):
    """nbnhhsh 模块测试 - 缩写翻译"""
    await tester.integrate("~nbnhhsh yyds", Contains("永远滴神"), "nbnhhsh 应返回缩写含义")
    await tester.integrate(
        "~nbnhhsh abcdefghijk_xyz",
        Contains("A boy can do everything for girl"),
        "nbnhhsh 应返回首段缩写的含义",
    )
    await tester.integrate(
        "~nbnhhsh zzz_no_such_abbr",
        Contains("没有匹配到拼音首字母缩写"),
        "nbnhhsh 空结果应提示未找到",
    )

    return tester


@func_case
async def test_idlist(tester: Tester):
    """idlist 模块测试 - 命令 ID 查询"""
    await tester.integrate("~idlist stone", Contains("stone"), "idlist 应返回匹配结果")
    await tester.integrate("~idlist nonexistent_xyz_12345", Contains("没有"), "idlist 未找到应提示")

    return tester


@func_case
async def test_emojimix(tester: Tester):
    """emojimix 模块测试 - Emoji 混合"""
    await tester.integrate("~emojimix", Contains("KE:image"), "emojimix 应输出图片")

    return tester
