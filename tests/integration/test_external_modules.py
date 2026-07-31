"""外部模块集成测试 - wiki, mcplayer, arcaea, mcmod 等。

mcserver 不在此列：它经 ``mcstatus`` 走 Minecraft 的原生协议（TCP/UDP）而非 HTTP，
``tests/fixtures/http/`` 的录制回放覆盖不到，结果只取决于目标服务器与本机网络，长期不稳定。
要重新纳入，须先为 ``modules.mcserver.server`` 的 ``query_java_server`` 一类入口备好替身。
"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_wiki(tester: Tester):
    """wiki 模块测试 - MediaWiki 查询"""
    await tester.integrate(
        "~wiki set https://zh.minecraft.wiki/api.php", Contains("成功设置起始 Wiki"), "wiki set 应提示成功"
    )
    await tester.integrate("~wiki", Contains("Minecraft"), "wiki 应返回 Minecraft Wiki 内容")
    await tester.integrate("~wiki Minecraft", Contains("Minecraft"), "wiki Minecraft 应返回页面内容")
    return tester


@func_case
async def test_mcplayer(tester: Tester):
    """mcplayer 模块测试 - MC 玩家查询"""
    await tester.integrate("~mcplayer Notch", Contains("Notch"), "mcplayer 应显示玩家名")
    return tester


@func_case
async def test_arcaea(tester: Tester):
    """arcaea 模块测试 - Arcaea 查询"""
    await tester.integrate("~arcaea download", Contains("最新版本"), "arcaea download 应显示版本号")
    return tester


@func_case
async def test_mcmod(tester: Tester):
    """mcmod 模块测试 - MCMOD 模组查询"""
    await tester.integrate("~mcmod 创建", Contains("Minecraft"), "mcmod 搜索应返回模组信息")
    return tester
