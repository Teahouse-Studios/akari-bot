"""modules/core 核心模块集成测试。"""

from core.tester import (
    func_case,
    Tester,
    All,
    Contains,
    ContainsAll,
    Empty,
    Not,
)
from modules.core.common_tools.help import regex_disable_prefixes


@func_case
async def test_version(tester: Tester):
    """version 命令测试"""
    await tester.integrate("~version", Contains("版本"), "version 应输出版本信息")

    return tester


@func_case
async def test_about(tester: Tester):
    """about 命令测试"""
    await tester.integrate("~about", Contains("AGPL-3.0"), "about 应显示关于信息")

    return tester


@func_case
async def test_help(tester: Tester):
    """help 命令测试"""
    await tester.integrate("~help", Contains("基础模块"), "help 应显示基础模块列表")
    await tester.integrate("~help help", Contains("--img"), "help 帮助应展示强制图片选项")
    await tester.integrate("~help version", Contains("version"), "help version 应显示版本帮助")
    await tester.integrate("~help version", Contains("版本号"), "help version 应包含版本号描述")
    await tester.integrate(
        "~help url-audit",
        ContainsAll("~url-audit allowlist", "~url-audit blocklist"),
        "合并后的 URL 模块帮助应展示允许列表与阻止列表子命令",
    )
    await tester.integrate("~help mojang-status", Contains("~mojang-status"), "help 应展示无文档模块自身的默认命令")
    await tester.integrate(
        "~help bilibili",
        ContainsAll("提示：", regex_disable_prefixes[0]),
        "带正则表达式的详细 help 应展示当前配置的临时关闭前缀",
    )

    return tester


@func_case
async def test_merged_about_bind_commands(tester: Tester):
    """并入 about 与 bind 的信息类子命令测试"""
    await tester.integrate(
        "~help about",
        ContainsAll("~about version", "~about ping", "~about status"),
        "合并后的 about 帮助应展示版本、状态与详细状态子命令",
    )
    await tester.integrate(
        "~help bind",
        Contains("~bind whoami"),
        "合并后的 bind 帮助应展示 whoami 子命令",
    )
    await tester.integrate("~about version", Contains("版本"), "about version 应输出版本信息")
    await tester.integrate(
        "~about ping",
        All(Contains("Pong!"), Not(Contains("WebRender")), Not(Contains("JobQueue"))),
        "about ping 应输出 Pong! 且不泄露服务器细节",
    )
    await tester.integrate(
        "~about status",
        ContainsAll("WebRender", "JobQueue", "Python"),
        "about status 应输出详细状态信息（以各语言保留的专有名词为锚点）",
    )
    await tester.integrate(
        "~status",
        ContainsAll("WebRender", "JobQueue"),
        "status 别名应指向 about status",
    )
    await tester.integrate("~bind whoami", Contains("用户组"), "bind whoami 应显示用户组信息")

    return tester


@func_case
async def test_merged_setup_commands(tester: Tester):
    """并入 setup 的前缀、语言与别名子命令测试"""
    await tester.integrate(
        "~help setup",
        ContainsAll("~setup prefix", "~setup locale", "~setup alias"),
        "合并后的 setup 帮助应展示前缀、语言与别名子命令",
    )
    await tester.integrate("~setup prefix list", Contains("前缀"), "setup prefix list 应显示前缀")
    await tester.integrate("~setup locale", Contains("简体中文"), "setup locale 应显示语言列表")
    await tester.integrate("~setup alias list", Contains("别名"), "setup alias list 应显示别名列表")

    return tester


@func_case
async def test_module_list(tester: Tester):
    """module list 命令测试"""
    await tester.integrate("~module list", Contains("当前可用的模块有"), "module list 应显示模块列表")

    return tester


@func_case
async def test_module_enable_disable(tester: Tester):
    """module enable/disable 命令测试"""
    await tester.integrate("~module disable coin", Contains("已关闭"), "module disable 应提示已关闭")
    await tester.integrate("~module enable coin", Contains("成功"), "module enable 应提示成功")
    await tester.integrate("~module enable version", Contains("已开启"), "module enable 已启用模块应提示已开启")
    await tester.integrate("~module disable version", Contains("基础模块"), "module disable 基础模块应提示基础模块")
    await tester.integrate(
        "~module enable nonexistent_xyz", Contains("不存在"), "module enable 不存在的模块应提示不存在"
    )

    return tester


@func_case
async def test_alias(tester: Tester):
    """alias 命令测试"""
    await tester.integrate("~alias list", Contains("别名"), "alias list 应显示别名列表")
    await tester.integrate("~alias add test_alias version", Contains("别名"), "alias add 应有提示")
    await tester.integrate("~alias remove test_alias", Contains("不存在"), "alias remove 不存在的别名应提示不存在")
    await tester.integrate("~alias reset", Contains("重置"), "alias reset 应提示重置")

    return tester


@func_case
async def test_prefix(tester: Tester):
    """prefix 命令测试"""
    await tester.integrate("~prefix list", Contains("前缀"), "prefix list 应显示前缀")
    await tester.integrate("~prefix add !", Contains("已添加"), "prefix add 应提示已添加")
    await tester.integrate("~prefix list", Contains("!"), "prefix list 应包含新前缀")
    await tester.integrate("~prefix remove !", Contains("已移除"), "prefix remove 应提示已移除")
    await tester.integrate("~prefix reset", Contains("已重置"), "prefix reset 应提示已重置")

    return tester


@func_case
async def test_unknown_command(tester: Tester):
    """未知命令测试"""
    await tester.integrate("~this_command_does_notexist_xyz_12345", Empty(), "未知命令应无输出")

    return tester


@func_case
async def test_ping(tester: Tester):
    """ping 命令测试"""
    await tester.integrate(
        "~ping",
        All(
            Contains("Pong!"),
            Not(Contains("WebRender")),
            Not(Contains("JobQueue")),
            Not(Contains("Python")),
        ),
        "ping 应输出 Pong! 且不泄露服务器细节",
    )

    return tester


@func_case
async def test_whoami(tester: Tester):
    """whoami 命令测试"""
    await tester.integrate("~whoami", Contains("ID"), "whoami 应显示用户 ID")
    await tester.integrate("~whoami", Contains("TEST|0"), "whoami 应显示 TEST|0")
    await tester.integrate("~whoami", Contains("用户组"), "whoami 应显示所属用户组")
    await tester.integrate("~whoami", Contains("场景组"), "whoami 应显示所属场景组")
    await tester.integrate("~whoami", Contains("TEST|Console|0"), "whoami 应列出场景组内已绑定的场景")

    return tester


@func_case
async def test_locale(tester: Tester):
    """locale 命令测试"""
    await tester.integrate("~locale", Contains("语言"), "locale 应显示语言信息")
    await tester.integrate("~locale", Contains("支持的语言列表"), "locale 应显示语言列表标题")
    await tester.integrate("~locale", Contains("简体中文"), "locale 应显示简体中文")

    return tester


@func_case
async def test_petal(tester: Tester):
    """petal 命令测试"""
    await tester.integrate("~petal", Contains("花瓣"), "petal 应显示花瓣信息")

    return tester
