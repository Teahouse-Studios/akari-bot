"""更多工具模块集成测试 - nbnhhsh、idlist。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_nbnhhsh(tester: Tester):
    """nbnhhsh 模块测试 - 缩写翻译"""
    await tester.integrate("~nbnhhsh yyds", Contains("可能"), "nbnhhsh 应返回缩写含义")
    return tester


@func_case
async def test_nbnhhsh_not_found(tester: Tester):
    """nbnhhsh 未找到测试"""
    await tester.integrate("~nbnhhsh abcdefghijk_xyz", Contains("没有"), "nbnhhsh 未找到应提示")
    return tester


@func_case
async def test_idlist(tester: Tester):
    """idlist 模块测试 - 命令 ID 查询"""
    await tester.integrate("~idlist stone", Contains("stone"), "idlist 应返回匹配结果")
    return tester


@func_case
async def test_idlist_not_found(tester: Tester):
    """idlist 未找到测试"""
    await tester.integrate("~idlist nonexistent_xyz_12345", Contains("没有"), "idlist 未找到应提示")
    return tester
