"""RSS 模块集成测试 - minecraft_news、feedback_news。"""

from core.loader import ModulesManager
from core.tester import func_case, Tester

RSS_MODULES = ("minecraft-news", "feedback-news")


def _module(name: str):
    return ModulesManager.return_modules_list().get(name)


def _test_rss_modules_registered():
    return all(_module(name) is not None for name in RSS_MODULES)


def _test_rss_modules_flagged():
    return all(_module(name).rss for name in RSS_MODULES)


def _test_rss_modules_have_schedules():
    return all(len(_module(name).schedule_list.set) > 0 for name in RSS_MODULES)


def _test_rss_modules_have_no_commands():
    return all(len(_module(name).command_list.set) == 0 for name in RSS_MODULES)


@func_case
async def test_minecraft_news(tester: Tester):
    """minecraft_news 与 feedback_news 注册结构测试"""
    await tester.test(_test_rss_modules_registered, "RSS 模块已注册测试")
    await tester.test(_test_rss_modules_flagged, "RSS 模块带 rss 标记测试")
    await tester.test(_test_rss_modules_have_schedules, "RSS 模块含定时任务测试")
    await tester.test(_test_rss_modules_have_no_commands, "RSS 模块无命令测试")
    return tester
