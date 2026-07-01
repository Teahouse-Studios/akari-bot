"""外部模块集成测试 - wiki, mcserver, mcplayer, arcaea, mcmod 等。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_wiki(tester: Tester):
    """wiki 模块测试 - MediaWiki 查询"""
    await tester.expect(
        "~wiki set https://zh.minecraft.wiki/api.php", Contains("成功设置起始 Wiki"), "wiki set 应提示成功"
    )
    await tester.expect("~wiki", Contains("Minecraft"), "wiki 应返回 Minecraft Wiki 内容")
    await tester.expect("~wiki Minecraft", Contains("Minecraft"), "wiki Minecraft 应返回页面内容")
    return tester


@func_case
async def test_mcserver(tester: Tester):
    """mcserver 模块测试 - MC 服务器查询"""
    await tester.expect("~mcserver mc.hypixel.net", Contains("在线玩家"), "mcserver 应显示在线玩家信息")
    return tester


@func_case
async def test_mcplayer(tester: Tester):
    """mcplayer 模块测试 - MC 玩家查询"""
    await tester.expect("~mcplayer Notch", Contains("Notch"), "mcplayer 应显示玩家名")
    return tester


@func_case
async def test_arcaea(tester: Tester):
    """arcaea 模块测试 - Arcaea 查询"""
    await tester.expect("~arcaea download", Contains("最新版本"), "arcaea download 应显示版本号")
    return tester


@func_case
async def test_mcmod(tester: Tester):
    """mcmod 模块测试 - MCMOD 模组查询"""
    await tester.expect("~mcmod 创建", Contains("Minecraft"), "mcmod 搜索应返回模组信息")
    return tester
