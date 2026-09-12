"""Wiki callback ownership and held-context lifecycle regression tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants import SessionContextUnavailable
from core.module_runtime import ModuleRuntimeManager
from core.server.lifecycle import BackgroundTaskLifecycle
from core.tester import func_case, Tester
from modules.wiki.wiki import (
    _build_forum_callback,
    _build_section_callback,
    _gather_background,
    _run_background_with_release,
    _start_background_with_release,
    query_pages,
)


class _ClickSession:
    def __init__(self, text: str):
        self.text = text

    def as_display(self, text_only: bool = False) -> str:
        return self.text


async def _test_section_callback_uses_click_session_and_frozen_page():
    page = SimpleNamespace(
        title="First page",
        sections=["First section"],
        info=SimpleNamespace(api="https://first.example/api.php"),
    )
    callback = _build_section_callback(page)

    # 模拟 query_pages 的下一轮循环覆写当前页对象；旧闭包会读取这些新值。
    page.title = "Last page"
    page.sections[0] = "Last section"
    page.info.api = "https://last.example/api.php"
    click = _ClickSession("1")

    with patch("modules.wiki.wiki.query_pages", new_callable=AsyncMock) as query:
        await callback(click)

    return query.await_args == (
        (click,),
        {"title": "First page#First section", "start_wiki_api": "https://first.example/api.php"},
    )


async def _test_section_callback_rejects_zero_index():
    page = SimpleNamespace(
        title="Page",
        sections=["First", "Last"],
        info=SimpleNamespace(api="https://example.com/api.php"),
    )
    callback = _build_section_callback(page)

    with patch("modules.wiki.wiki.query_pages", new_callable=AsyncMock) as query:
        await callback(_ClickSession("0"))

    return query.await_count == 0


async def _test_forum_callback_uses_click_session_and_frozen_page():
    page = SimpleNamespace(
        forum_data={"#": {"data": ["title"]}, "1": {"text": "First topic", "data": []}},
        info=SimpleNamespace(api="https://first.example/api.php"),
    )
    callback = _build_forum_callback(page)

    page.forum_data["1"]["text"] = "Last topic"
    page.info.api = "https://last.example/api.php"
    click = _ClickSession("1")

    with patch("modules.wiki.wiki.query_pages", new_callable=AsyncMock) as query:
        await callback(click)

    return query.await_args == (
        (click,),
        {"title": "First topic", "start_wiki_api": "https://first.example/api.php"},
    )


async def _test_background_failure_releases_context():
    session = SimpleNamespace(release=AsyncMock())

    async def fail():
        raise RuntimeError("background failure")

    try:
        await _run_background_with_release(session, fail())
    except RuntimeError:
        return session.release.await_count == 1
    return False


async def _test_background_failure_waits_for_siblings_before_release():
    sibling_done = False
    release_observed_sibling = False

    async def release():
        nonlocal release_observed_sibling
        release_observed_sibling = sibling_done

    session = SimpleNamespace(release=release)

    async def fail():
        raise RuntimeError("background failure")

    async def sibling():
        nonlocal sibling_done
        await asyncio.sleep(0)
        sibling_done = True

    try:
        await _run_background_with_release(session, _gather_background(fail(), sibling()))
    except RuntimeError:
        return sibling_done and release_observed_sibling
    return False


async def _test_background_spawn_failure_rolls_back_hold():
    session = SimpleNamespace(hold=AsyncMock(), release=AsyncMock())

    async def idle():
        await asyncio.sleep(0)

    with patch("core.module_runtime.asyncio.create_task", side_effect=RuntimeError("loop closed")):
        try:
            await _start_background_with_release(session, idle, name="wiki-spawn-failure")
        except RuntimeError:
            return session.hold.await_count == 1 and session.release.await_count == 1
    return False


async def _test_background_hold_failure_skips_creation():
    session = SimpleNamespace(
        hold=AsyncMock(side_effect=SessionContextUnavailable("Session not found in context")),
        release=AsyncMock(),
    )
    awaitable_factory = AsyncMock()

    task = await _start_background_with_release(session, awaitable_factory, name="wiki-context-unavailable")

    return task is None and awaitable_factory.await_count == 0 and session.release.await_count == 0


async def _test_background_task_is_retained_until_completion():
    gate = asyncio.Event()
    session = SimpleNamespace(hold=AsyncMock(), release=AsyncMock())

    async def wait_for_gate():
        await gate.wait()

    task = await _start_background_with_release(session, wait_for_gate, name="wiki-retained-task")
    retained = task in ModuleRuntimeManager.get_or_create("wiki").tasks
    gate.set()
    await task
    await asyncio.sleep(0)
    return (
        retained and task not in ModuleRuntimeManager.get_or_create("wiki").tasks and session.release.await_count == 1
    )


async def _test_query_pages_holds_context_for_entire_query():
    events = []

    class HeldSession(MessageSession):
        async def hold(self):
            events.append("hold")

        async def release(self):
            events.append("release")

    session = HeldSession(
        SessionInfo(
            target_id="TEST|Group|wiki-query-hold",
            target_from="TEST|Group",
            client_name="TEST",
        )
    )

    async def query(*args, **kwargs):
        events.append("query")
        return kwargs["title"]

    with patch("modules.wiki.wiki._query_pages_impl", new=query):
        result = await query_pages(session, title="Page")

    return result == "Page" and events == ["hold", "query", "release"]


async def _test_query_pages_skips_when_context_is_unavailable():
    class HeldSession(MessageSession):
        async def hold(self):
            raise SessionContextUnavailable("Session not found in context")

    session = HeldSession(
        SessionInfo(
            target_id="TEST|Group|wiki-query-unavailable",
            target_from="TEST|Group",
            client_name="TEST",
        )
    )
    query = AsyncMock()
    with patch("modules.wiki.wiki._query_pages_impl", new=query):
        result = await query_pages(session, title="Page")

    return result is None and query.await_count == 0


async def _test_background_cleanup_cancels_and_releases():
    gate = asyncio.Event()
    session = SimpleNamespace(hold=AsyncMock(), release=AsyncMock())

    async def wait_forever():
        await gate.wait()

    task = await _start_background_with_release(session, wait_forever, name="wiki-cleanup-task")
    runtime = ModuleRuntimeManager.get_or_create("wiki")
    await runtime.stop("test")
    runtime.activate()
    await asyncio.sleep(0)
    return task.cancelled() and task not in runtime.tasks and session.release.await_count == 1


async def _test_background_tasks_are_runtime_owned():
    return "module:wiki-background" not in BackgroundTaskLifecycle._cleanup_hooks


@func_case
async def test_wiki_lifecycle(tester: Tester):
    await tester.test(_test_section_callback_uses_click_session_and_frozen_page, "章节回调会话与闭包冻结")
    await tester.test(_test_section_callback_rejects_zero_index, "章节回调拒绝零号索引")
    await tester.test(_test_forum_callback_uses_click_session_and_frozen_page, "论坛回调会话与闭包冻结")
    await tester.test(_test_background_failure_releases_context, "Wiki 后台异常释放上下文")
    await tester.test(_test_background_failure_waits_for_siblings_before_release, "Wiki 后台异常等待同批任务")
    await tester.test(_test_background_spawn_failure_rolls_back_hold, "Wiki 后台创建失败回滚 hold")
    await tester.test(_test_background_hold_failure_skips_creation, "Wiki 上下文不可用时跳过后台任务")
    await tester.test(_test_background_task_is_retained_until_completion, "Wiki 后台任务持有引用")
    await tester.test(_test_query_pages_holds_context_for_entire_query, "Wiki 查询全程保持上下文")
    await tester.test(_test_query_pages_skips_when_context_is_unavailable, "Wiki 查询上下文不可用时跳过")
    await tester.test(_test_background_cleanup_cancels_and_releases, "Wiki 后台清理取消并释放")
    await tester.test(_test_background_tasks_are_runtime_owned, "Wiki 后台任务由 runtime 托管")
    return tester
