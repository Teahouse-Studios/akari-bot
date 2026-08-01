"""wiki 模块高级集成测试 - search、iw、headers、prefix。

wiki 模块的绝大多数子命令都要求当前场景已设置起始 Wiki，否则一律直接返回提示。
每个 func_case 运行前数据库都会重建，场景状态不会跨用例保留，因此每个用例都需
自行完成设置。相关请求由 tests/fixtures/http/ 下的录制响应提供，不依赖实时网络。
"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)

START_WIKI = "~wiki set https://zh.minecraft.wiki/api.php"


@func_case
async def test_wiki_search(tester: Tester):
    """wiki search 搜索测试"""
    await tester.integrate(START_WIKI, Contains("成功设置起始 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki search Minecraft", Contains("搜索结果"), "wiki search 应返回搜索结果")
    return tester


@func_case
async def test_wiki_iw_manage(tester: Tester):
    """wiki iw 管理测试"""
    await tester.integrate("~wiki iw list", Contains("Interwiki"), "wiki iw list 应显示列表")
    return tester


@func_case
async def test_wiki_headers_manage(tester: Tester):
    """wiki headers 管理测试"""
    await tester.integrate(START_WIKI, Contains("成功设置起始 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki headers show", Contains("请求标头"), "wiki headers show 应显示标头")
    return tester


@func_case
async def test_wiki_prefix_manage(tester: Tester):
    """wiki prefix 管理测试"""
    await tester.integrate(START_WIKI, Contains("成功设置起始 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki prefix set Test", Contains("前缀"), "wiki prefix set 应提示设置结果")
    await tester.integrate("~wiki prefix reset", Contains("重置"), "wiki prefix reset 应提示重置")
    return tester


@func_case
async def test_wiki_page_info(tester: Tester):
    """wiki 页面信息测试"""
    await tester.integrate(START_WIKI, Contains("成功设置起始 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki Minecraft", Contains("Minecraft"), "wiki 查询应返回页面信息")
    return tester


@func_case
async def test_wiki_not_found(tester: Tester):
    """wiki 不存在页面测试"""
    await tester.integrate(START_WIKI, Contains("成功设置起始 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki nonexistent_page_xyz_12345", Contains("未找到"), "不存在的页面应提示未找到")
    return tester


@func_case
async def test_wiki_start_wiki_not_set(tester: Tester):
    """未设置起始 Wiki 提示测试

    推荐绑定的按钮只在 QQ 官方机器人上附加，测试会话的客户端名恒为 TEST，
    故此处只求证提示本身照常发出，按钮相关的判据见 tests/unit/test_wiki_recommend.py。
    """
    await tester.integrate("~wiki Minecraft", Contains("没有设置起始 Wiki"), "wiki 查询应提示未设置")
    await tester.integrate("~wiki search Minecraft", Contains("没有设置起始 Wiki"), "wiki search 应提示未设置")
    return tester
