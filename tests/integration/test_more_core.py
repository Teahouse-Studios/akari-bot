"""modules/core 更多核心模块集成测试 - locale、petal、analytics。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
)


@func_case
async def test_locale_set(tester: Tester):
    """locale 设置语言测试

    切换生效后的回执使用目标语言，因此两步需分别以对应语言的文案断言。
    """
    await tester.integrate("~locale en_us", Contains("Success"), "locale 切换英文后应以英文回执")
    await tester.integrate("~locale zh_cn", Contains("成功"), "locale 恢复中文后应以中文回执")
    return tester


@func_case
async def test_petal_sign(tester: Tester):
    """petal sign 签到测试"""
    await tester.integrate("~petal sign", Contains("花瓣"), "petal sign 应提示花瓣信息")
    return tester


@func_case
async def test_petal_view(tester: Tester):
    """petal 查看花瓣测试"""
    await tester.integrate("~petal", Contains("花瓣"), "petal 应显示花瓣数量")
    return tester


@func_case
async def test_version(tester: Tester):
    """version 版本信息测试

    version 命令不接受参数。部署方式不同时回执分为版本号与「无法获取版本号」两种，
    两者均含「版本」，故断言对部署环境不敏感。
    """
    await tester.integrate("~version", Contains("版本"), "version 应显示版本信息")
    return tester
