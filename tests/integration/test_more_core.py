"""modules/core 更多核心模块集成测试 - locale、petal、analytics、say。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
    Match,
)


@func_case
async def test_locale_set(tester: Tester):
    """locale 设置语言测试"""
    await tester.integrate("~locale en_us", Contains("Success"), "locale 切换英文后应以英文回执")
    await tester.integrate("~locale zh_cn", Contains("成功"), "locale 恢复中文后应以中文回执")
    return tester


@func_case
async def test_petal_sign(tester: Tester):
    """petal sign 签到测试"""
    await tester.integrate("~petal sign", Contains("花瓣"), "petal sign 应提示花瓣信息")
    return tester


@func_case
async def test_say(tester: Tester):
    """say 命令测试"""
    await tester.integrate(r"~say a\b", Match(r"a\b"), "say 应原样发出单个反斜杠")
    await tester.integrate(r"~say a\\b", Match(r"a\\b"), "say 应原样发出连续的两个反斜杠")
    await tester.integrate(r"~say \d+", Match(r"\d+"), "say 应原样发出正则式反斜杠")
    await tester.integrate("~say TEST|0 hi", Match("<AT:TEST|0> hi"), "say 应照旧把发送者 ID 转换为 AT 码")
    return tester
