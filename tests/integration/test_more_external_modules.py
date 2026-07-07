"""更多外部模块集成测试 - emojimix, oba 等。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_emojimix(tester: Tester):
    """emojimix 模块测试 - Emoji 混合"""
    await tester.integrate("~emojimix", Contains("KE:image"), "emojimix 应输出图片")
    return tester


@func_case
async def test_oba(tester: Tester):
    """oba 模块测试 - OpenBMCLAPI 状态"""
    await tester.integrate("~oba status", Contains("在线节点"), "oba status 应显示节点信息")
    return tester
