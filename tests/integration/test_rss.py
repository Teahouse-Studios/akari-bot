"""RSS 模块集成测试 - minecraft_news。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_minecraft_news(tester: Tester):
    """minecraft_news 模块测试"""
    await tester.integrate("~minecraft_news", Contains("Minecraft"), "minecraft_news 应有输出")
    return tester
