"""modules/core 更多核心模块集成测试 - locale、petal、analytics。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_locale_set(tester: Tester):
    """locale 设置语言测试"""
    await tester.expect("~locale en_us", Contains("语言"), "locale set 应提示语言设置")
    await tester.expect("~locale zh_cn", Contains("语言"), "locale 恢复中文")
    return tester


@func_case
async def test_petal_sign(tester: Tester):
    """petal sign 签到测试"""
    await tester.expect("~petal sign", Contains("花瓣"), "petal sign 应提示花瓣信息")
    return tester


@func_case
async def test_petal_view(tester: Tester):
    """petal 查看花瓣测试"""
    await tester.expect("~petal", Contains("花瓣"), "petal 应显示花瓣数量")
    return tester


@func_case
async def test_version_sys(tester: Tester):
    """version sys 系统信息测试"""
    await tester.expect("~version sys", Contains("系统"), "version sys 应显示系统信息")
    return tester
