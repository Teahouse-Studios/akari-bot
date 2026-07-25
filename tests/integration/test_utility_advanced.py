"""工具模块高级集成测试 - dice 复杂表达式、hash。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
    Regex,
)


@func_case
async def test_dice_complex(tester: Tester):
    """dice 复杂表达式测试"""
    await tester.integrate("~dice 4d6kh3", Contains("掷得"), "dice 4d6kh3 应输出结果")
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
    return tester


@func_case
async def test_hash_md5(tester: Tester):
    """hash md5 测试"""
    await tester.integrate("~hash md5 hello", Contains("d41d8cd98f00b204e9800998ecf8427e"), "hash md5 应输出哈希值")
    return tester


@func_case
async def test_hash_sha256(tester: Tester):
    """hash sha256 测试"""
    await tester.integrate("~hash sha256 hello", Regex(r"[0-9a-f]{64}"), "hash sha256 应输出64位哈希值")
    return tester
