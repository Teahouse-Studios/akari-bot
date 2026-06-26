"""modules/core 核心模块集成测试。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
    Empty,
)


@func_case
async def test_version(tester: Tester):
    """version 命令测试"""
    await tester.expect("~version", Contains("版本"), "version 应输出版本信息")

    return tester


@func_case
async def test_help(tester: Tester):
    """help 命令测试"""
    await tester.expect("~help", Contains("基础模块"), "help 应显示基础模块列表")
    await tester.expect("~help version", Contains("version"), "help version 应显示版本帮助")
    await tester.expect("~help version", Contains("版本号"), "help version 应包含版本号描述")

    return tester


@func_case
async def test_module_list(tester: Tester):
    """module list 命令测试"""
    await tester.expect("~module list", Contains("当前可用的模块有"), "module list 应显示模块列表")

    return tester


@func_case
async def test_module_enable_disable(tester: Tester):
    """module enable/disable 命令测试"""
    await tester.expect("~module disable coin", Contains("已关闭"), "module disable 应提示已关闭")
    await tester.expect("~module enable coin", Contains("成功"), "module enable 应提示成功")
    await tester.expect("~module enable version", Contains("已开启"), "module enable 已启用模块应提示已开启")
    await tester.expect("~module disable version", Contains("基础模块"), "module disable 基础模块应提示基础模块")
    await tester.expect("~module enable nonexistent_xyz", Contains("不存在"), "module enable 不存在的模块应提示不存在")

    return tester


@func_case
async def test_alias(tester: Tester):
    """alias 命令测试"""
    await tester.expect("~alias list", Contains("别名"), "alias list 应显示别名列表")
    await tester.expect("~alias add test_alias version", Contains("别名"), "alias add 应有提示")
    await tester.expect("~alias remove test_alias", Contains("不存在"), "alias remove 不存在的别名应提示不存在")
    await tester.expect("~alias reset", Contains("重置"), "alias reset 应提示重置")

    return tester


@func_case
async def test_prefix(tester: Tester):
    """prefix 命令测试"""
    await tester.expect("~prefix list", Contains("前缀"), "prefix list 应显示前缀")
    await tester.expect("~prefix add !", Contains("已添加"), "prefix add 应提示已添加")
    await tester.expect("~prefix list", Contains("!"), "prefix list 应包含新前缀")
    await tester.expect("~prefix remove !", Contains("已移除"), "prefix remove 应提示已移除")
    await tester.expect("~prefix reset", Contains("已重置"), "prefix reset 应提示已重置")

    return tester


@func_case
async def test_unknown_command(tester: Tester):
    """未知命令测试"""
    await tester.expect("~this_command_does_notexist_xyz_12345", Empty(), "未知命令应无输出")

    return tester


@func_case
async def test_ping(tester: Tester):
    """ping 命令测试"""
    await tester.expect("~ping", Contains("Pong!"), "ping 应输出 Pong!")
    await tester.expect("~ping", Contains("Python 版本"), "ping 应显示 Python 版本")

    return tester


@func_case
async def test_whoami(tester: Tester):
    """whoami 命令测试"""
    await tester.expect("~whoami", Contains("ID"), "whoami 应显示用户 ID")
    await tester.expect("~whoami", Contains("TEST|0"), "whoami 应显示 TEST|0")

    return tester


@func_case
async def test_locale(tester: Tester):
    """locale 命令测试"""
    await tester.expect("~locale", Contains("语言"), "locale 应显示语言信息")
    await tester.expect("~locale", Contains("简体中文"), "locale 应显示简体中文")

    return tester


@func_case
async def test_petal(tester: Tester):
    """petal 命令测试"""
    await tester.expect("~petal", Contains("花瓣"), "petal 应显示花瓣信息")

    return tester


@func_case
async def test_admin(tester: Tester):
    """admin 命令测试"""
    await tester.expect("~admin list", Contains("管理员"), "admin list 应显示管理员信息")

    return tester
