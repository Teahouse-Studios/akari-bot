"""定时任务与钩子的集成测试。

这些模块不由消息触发，注册结构正确并不代表功能可用，因此此处直接调用它们的函数，
并断言可观察的副作用（推送入队、持久化列表更新、缓存目录重建等）。

生产环境中定时任务受触发器择时执行，且普遍带有两类闸门：
    1. 首轮静默（startup_mute），避免机器人重启后重复刷屏；
    2. 已推送去重，依赖持久化列表。
测试通过 force_run_schedule 清除这两类闸门后立即触发，无需等待任何时间阈值。

外部请求全部由 tests/fixtures/ 下的语料提供，并以 strict_http 禁止回落到真实网络：
未录制的 URL 会立即失败，而不是带着重试与超时把用例拖上一分多钟。
"""

from core.alive import Alive
from core.constants.path import cache_path
from core.database.models import JobQueuesTable
from core.tester import func_case, Tester
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.scheduler import (
    force_run_schedule,
    get_module_hooks,
    run_hook,
    strict_http,
)

SUBSCRIBER_TARGET = "TEST|Group|sched"


async def _subscribe(module_name: str):
    """建立一个订阅了指定模块且客户端在线的场景。

    post_message 在未指定会话时按模块名查订阅者，且会跳过掉线的客户端；
    两者缺一，任务即便正常执行也不会留下任何可观察的推送。
    """
    await TestDataFactory.ensure_target(SUBSCRIBER_TARGET, modules=[module_name])
    Alive.refresh_alive("TEST", target_prefix_list=["TEST|Group"], sender_prefix_list=["TEST"])


async def _posted_count() -> int:
    return await JobQueuesTable.filter(action="post_message").count()


async def _reset_queue():
    await JobQueuesTable.all().delete()


async def _run(module_name: str, module_path: str | None = None, stored_keys: tuple[str, ...] = ()) -> list[dict]:
    """清空队列后强制触发指定模块的定时任务。"""
    await _reset_queue()
    await _subscribe(module_name)
    with strict_http():
        return await force_run_schedule(module_name, module_path, stored_keys, timeout=25)


def _no_error(results: list[dict]) -> bool:
    return bool(results) and all(r["success"] for r in results)


async def _test_arcaea_rss_posts_new_version():
    """arcaea_rss: 发现新版本时应推送"""
    results = await _run("arcaea_rss", "modules.arcaea_rss", ("arcaea_rss",))
    return _no_error(results) and await _posted_count() >= 1


async def _test_arcaea_rss_deduplicates():
    """arcaea_rss: 版本已记录时不应重复推送"""
    await _run("arcaea_rss", "modules.arcaea_rss", ("arcaea_rss",))
    # 第二次不清空持久化列表，仅重置队列，验证去重生效。
    await _reset_queue()
    with strict_http():
        results = await force_run_schedule("arcaea_rss", "modules.arcaea_rss", (), timeout=25)
    return _no_error(results) and await _posted_count() == 0


async def _test_mcv_rss_posts_versions():
    """mcv_rss: 应推送最新正式版与快照版"""
    results = await _run("mcv_rss", "modules.mcv_rss", ("mcv_rss", "mcnews"))
    return _no_error(results) and await _posted_count() >= 2


async def _test_minecraft_news_posts_articles():
    """minecraft_news: 应逐条推送未记录过的文章"""
    results = await _run("minecraft_news", "modules.minecraft_news", ("mcnews",))
    return _no_error(results) and await _posted_count() >= 1


async def _test_minecraft_news_deduplicates():
    """minecraft_news: 已记录的文章不应重复推送"""
    await _run("minecraft_news", "modules.minecraft_news", ("mcnews",))
    await _reset_queue()
    with strict_http():
        results = await force_run_schedule("minecraft_news", "modules.minecraft_news", (), timeout=25)
    return _no_error(results) and await _posted_count() == 0


async def _test_feedback_news_posts_articles():
    """feedback_news: 应推送反馈站的新文章"""
    results = await _run("feedback_news", "modules.minecraft_news", ("mcfeedbacknews",))
    return _no_error(results) and await _posted_count() >= 1


async def _test_teahouse_weekly_posts():
    """teahouse_weekly_rss: 应推送茶馆周报"""
    results = await _run("teahouse_weekly_rss")
    return _no_error(results) and await _posted_count() >= 1


async def _test_purge_recreates_cache_dir():
    """purge: 应清空并重建缓存目录"""
    cache_path.mkdir(parents=True, exist_ok=True)
    probe = cache_path / "purge_probe.tmp"
    probe.write_text("stale", encoding="utf-8")

    with strict_http():
        results = await force_run_schedule("purge", timeout=25)

    # 目录需保留（后续写缓存依赖它存在），但其中的残留文件应被清除。
    return _no_error(results) and cache_path.exists() and not probe.exists()


async def _test_schedules_report_failure_explicitly():
    """未录制语料时应显式失败，而非静默回落到真实网络"""
    from core.constants.info import Info
    from core.utils.http import get_url

    with strict_http():
        if not Info.http_mock_strict:
            return False
        try:
            await get_url("https://never-recorded.example/nothing", attempt=1)
        except Exception as e:
            return "No HTTP fixture recorded" in str(e)
    return False


async def _test_wikilog_keepalive_hook_runs():
    """wikilog.keepalive: 无配置时应正常返回而不抛错"""
    result = await run_hook("wikilog.keepalive")
    return result["success"]


async def _test_wiki_autosearch_hook_returns_titles():
    """wiki.autosearch: 应按标题返回搜索候选"""
    from core.builtins.session.info import SessionInfo

    await TestDataFactory.ensure_target(SUBSCRIBER_TARGET, modules=["wiki"])
    session = await SessionInfo.assign(
        target_id=SUBSCRIBER_TARGET,
        client_name="TEST",
        target_from="TEST|Group",
        sender_id="TEST|0",
        sender_from="TEST",
    )
    from modules.wiki.database.models import WikiTargetInfo

    target = await WikiTargetInfo.get_by_target_id(SUBSCRIBER_TARGET)
    await target.add_start_wiki("https://zh.minecraft.wiki/api.php")

    with strict_http():
        result = await run_hook("wiki.autosearch", {"title": "Minecraft"}, session_info=session)
    return result["success"] and isinstance(result["result"], list) and len(result["result"]) > 0


async def _test_wiki_custom_iw_hook_returns_list():
    """wiki.auto_get_custom_iw_list: 应返回自定义 Interwiki 列表"""
    from core.builtins.session.info import SessionInfo

    session = await SessionInfo.assign(
        target_id=SUBSCRIBER_TARGET,
        client_name="TEST",
        target_from="TEST|Group",
        sender_id="TEST|0",
        sender_from="TEST",
    )
    result = await run_hook("wiki.auto_get_custom_iw_list", session_info=session)
    return result["success"] and isinstance(result["result"], list)


async def _test_wiki_bot_login_hook_accepts_cookies():
    """wiki_bot.login_wiki_bots: 应接受 cookies 参数并正常返回"""
    result = await run_hook("wiki_bot.login_wiki_bots", {"cookies": {"session": "test"}})
    return result["success"]


def _test_all_named_hooks_are_reachable():
    """全部具名钩子都应能按名取到，供跨进程 trigger_hook 分发"""
    hooks = get_module_hooks()
    expected = {
        "wiki.autosearch",
        "wiki.auto_get_custom_iw_list",
        "wiki_bot.login_wiki_bots",
        "wikilog.keepalive",
    }
    return expected.issubset(set(hooks))


@func_case
async def test_scheduled_tasks(tester: Tester):
    """定时任务手动触发测试"""
    await tester.test(_test_arcaea_rss_posts_new_version, "arcaea_rss 推送新版本测试")
    await tester.test(_test_arcaea_rss_deduplicates, "arcaea_rss 去重测试")
    await tester.test(_test_mcv_rss_posts_versions, "mcv_rss 推送版本测试")
    await tester.test(_test_minecraft_news_posts_articles, "minecraft_news 推送文章测试")
    await tester.test(_test_minecraft_news_deduplicates, "minecraft_news 去重测试")
    await tester.test(_test_feedback_news_posts_articles, "feedback_news 推送文章测试")
    await tester.test(_test_teahouse_weekly_posts, "teahouse_weekly_rss 推送测试")
    await tester.test(_test_purge_recreates_cache_dir, "purge 重建缓存目录测试")
    await tester.test(_test_schedules_report_failure_explicitly, "未录制语料显式失败测试")

    return tester


@func_case
async def test_module_hooks(tester: Tester):
    """模块钩子手动触发测试"""
    await tester.test(_test_all_named_hooks_are_reachable, "具名钩子可达测试")
    await tester.test(_test_wikilog_keepalive_hook_runs, "wikilog.keepalive 触发测试")
    await tester.test(_test_wiki_autosearch_hook_returns_titles, "wiki.autosearch 返回候选测试")
    await tester.test(_test_wiki_custom_iw_hook_returns_list, "wiki.auto_get_custom_iw_list 返回列表测试")
    await tester.test(_test_wiki_bot_login_hook_accepts_cookies, "wiki_bot.login_wiki_bots 触发测试")

    return tester
