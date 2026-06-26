"""wiki 模块高级集成测试 - search、iw、headers、prefix。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_wiki_search(tester: Tester):
    """wiki search 搜索测试"""
    await tester.expect("~wiki set https://zh.minecraft.wiki/api.php", Contains("成功设置起始 Wiki"), "设置 Wiki")
    await tester.expect("~wiki search Minecraft", Contains("搜索"), "wiki search 应返回搜索结果")
    return tester


@func_case
async def test_wiki_iw_manage(tester: Tester):
    """wiki iw 管理测试"""
    await tester.expect("~wiki iw list", Contains("Interwiki"), "wiki iw list 应显示列表")
    return tester


@func_case
async def test_wiki_headers_manage(tester: Tester):
    """wiki headers 管理测试"""
    await tester.expect("~wiki headers list", Contains("请求标头"), "wiki headers list 应显示标头")
    return tester


@func_case
async def test_wiki_prefix_manage(tester: Tester):
    """wiki prefix 管理测试"""
    await tester.expect("~wiki prefix Test", Contains("前缀"), "wiki prefix 应提示设置结果")
    await tester.expect("~wiki prefix reset", Contains("重置"), "wiki prefix reset 应提示重置")
    return tester


@func_case
async def test_wiki_page_info(tester: Tester):
    """wiki page 页面信息测试"""
    await tester.expect("~wiki page Minecraft", Contains("Minecraft"), "wiki page 应返回页面信息")
    return tester


@func_case
async def test_wiki_not_found(tester: Tester):
    """wiki 不存在页面测试"""
    await tester.expect("~wiki nonexistent_page_xyz_12345", Contains("未找到"), "不存在的页面应提示未找到")
    return tester
