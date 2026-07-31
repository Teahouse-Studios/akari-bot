"""RSS 模块集成测试 - minecraft_news、feedback_news。

这两个模块只注册定时任务，不提供任何命令，无法通过发送指令触发。它们的推送内容
依赖外部站点的实时更新，也不适合以固定语料断言。因此此处只校验注册结构本身：
模块存在、被标记为 RSS、注册了定时任务且未注册命令。
"""

from core.loader import ModulesManager
from core.tester import func_case, Tester

RSS_MODULES = ("minecraft_news", "feedback_news")


def _module(name: str):
    return ModulesManager.return_modules_list().get(name)


def _test_rss_modules_registered():
    """RSS 模块应完成注册"""
    return all(_module(name) is not None for name in RSS_MODULES)


def _test_rss_modules_flagged():
    """RSS 模块应带有 rss 标记，供推送开关识别"""
    return all(_module(name).rss for name in RSS_MODULES)


def _test_rss_modules_have_schedules():
    """RSS 模块应注册定时任务，否则推送不会发生"""
    return all(len(_module(name).schedule_list.set) > 0 for name in RSS_MODULES)


def _test_rss_modules_have_no_commands():
    """RSS 模块不提供命令，以指令方式调用不会有任何输出"""
    return all(len(_module(name).command_list.set) == 0 for name in RSS_MODULES)


@func_case
async def test_minecraft_news(tester: Tester):
    """minecraft_news 与 feedback_news 注册结构测试"""
    await tester.test(_test_rss_modules_registered, "RSS 模块已注册测试")
    await tester.test(_test_rss_modules_flagged, "RSS 模块带 rss 标记测试")
    await tester.test(_test_rss_modules_have_schedules, "RSS 模块含定时任务测试")
    await tester.test(_test_rss_modules_have_no_commands, "RSS 模块无命令测试")
    return tester
