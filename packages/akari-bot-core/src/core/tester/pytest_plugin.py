"""tests/unit 的 pytest 插件：收集 ``@func_case`` 入口、引导运行时并施加超时。

根级 conftest.py 通过 ``pytest_plugins`` 注册本模块。用例在会话事件循环中执行，
全程只有一个循环，与生产环境里 Tortoise 连接、HTTP 客户端和队列 peer 的绑定
方式一致；``@func_case`` 入口内的 :meth:`Tester.test` 失败即 pytest 断言失败。
"""

import asyncio
import inspect
import os
from collections.abc import Awaitable, Callable
from types import FunctionType
from typing import Any

import pytest

from core.tester.tasks import cancel_orphan_tasks, current_tasks
from core.tester.tester import Tester
from core.tester.timing import TIME_SCALE

DEFAULT_TEST_TIMEOUT = 120.0 * min(TIME_SCALE, 5.0)
TIMEOUT_ENV = "AKARI_TEST_TIMEOUT"
FUNC_CASE_ATTR = "_func_case"
TASK_BASELINE = pytest.StashKey[set[asyncio.Task]]()

_session_loop: asyncio.AbstractEventLoop | None = None


def get_session_loop() -> asyncio.AbstractEventLoop:
    """返回整个测试会话共用的事件循环，不存在时新建并设为当前循环。"""
    global _session_loop
    if _session_loop is None or _session_loop.is_closed():
        _session_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_session_loop)
    return _session_loop


def run_in_session_loop(awaitable: Awaitable[Any]) -> Any:
    """在会话事件循环中执行协程并返回其结果。"""
    return get_session_loop().run_until_complete(awaitable)


def close_session_loop() -> None:
    """关闭会话事件循环，并回收残留任务。"""
    global _session_loop
    loop, _session_loop = _session_loop, None
    if loop is None or loop.is_closed():
        return
    try:
        loop.run_until_complete(cancel_orphan_tasks())
    except Exception:
        pass
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def _bootstrap_runtime() -> None:
    """建库并加载模块、语言包与录制的 HTTP 响应，须早于用例收集。"""
    from core.tester.mock.database import get_last_init_error, init_db
    from core.tester.mock.loader import load_modules
    from core.tester.mock.random import Random

    if not await init_db():
        raise RuntimeError(f"测试数据库初始化失败。\n{get_last_init_error()}")
    await load_modules(show_logs=False, monkey_patches={"Random": Random()})


async def _shutdown_runtime() -> None:
    from core.tester.mock.database import close_db

    await cancel_orphan_tasks()
    await close_db()


def resolve_timeout(item: pytest.Item) -> float:
    """取单个测试的超时秒数：标记优先于环境变量，其次为默认值。"""
    marker = item.get_closest_marker("akari_timeout")
    if marker is not None and marker.args:
        return float(marker.args[0])
    configured = os.environ.get(TIMEOUT_ENV, "").strip()
    if configured:
        try:
            return max(1.0, float(configured))
        except ValueError:
            pass
    return DEFAULT_TEST_TIMEOUT


def pytest_sessionstart(session: pytest.Session) -> None:
    try:
        run_in_session_loop(_bootstrap_runtime())
    except Exception as error:
        pytest.exit(f"测试环境初始化失败：{error}", returncode=1)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    try:
        run_in_session_loop(_shutdown_runtime())
    except Exception:
        pass
    finally:
        close_session_loop()


async def prepare_runtime() -> None:
    """重建内存数据库与模块注册表，使每个测试项都有自己的初始状态。"""
    from core.loader import ModulesManager
    from core.tester.mock.database import close_db, get_last_init_error, init_db

    await close_db()
    if not await init_db():
        raise RuntimeError(f"测试数据库初始化失败。\n{get_last_init_error()}")
    # 模块注册表与 hook 订阅是进程级状态，用例可能将其改写或关闭。
    ModulesManager.refresh()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    item.stash[TASK_BASELINE] = run_in_session_loop(current_tasks())
    run_in_session_loop(prepare_runtime())


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:
    baseline = item.stash.get(TASK_BASELINE, None)
    if run_in_session_loop(cancel_orphan_tasks(baseline)):
        return
    # 未完成取消收尾的任务会带着已关闭的数据库上下文继续运行，后续用例不再可信。
    pytest.exit("用例遗留的后台任务未能完成取消收尾。", returncode=1)


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """在会话事件循环中执行测试，并施加超时。

    同步测试同样在循环内执行：被测代码（如 discord.ui.View）会向
    运行中的循环取事件循环。
    """
    kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    run_test_call(pyfuncitem.obj, kwargs, resolve_timeout(pyfuncitem))
    return True


async def _call_sync_test(fn: Callable[..., Any], kwargs: dict[str, Any]) -> Any:
    return fn(**kwargs)


class TestTimeout(Exception):
    """单个测试超过时限。"""


async def run_with_timeout(awaitable: Awaitable[Any], timeout: float) -> None:
    """等待测试完成，超过时限时抛出 :class:`TestTimeout` 并取消测试。"""
    scope = asyncio.timeout(timeout)
    try:
        async with scope:
            await awaitable
    except TimeoutError:
        # 测试自己抛出的 TimeoutError 不是测试超时，只有本上下文到期才判定。
        if scope.expired():
            raise TestTimeout(timeout) from None
        raise


def run_test_call(fn: Callable[..., Any], kwargs: dict[str, Any], timeout: float) -> None:
    """在会话事件循环中执行单个测试，超时判定为测试失败。"""
    awaitable = fn(**kwargs) if inspect.iscoroutinefunction(fn) else _call_sync_test(fn, kwargs)
    try:
        run_in_session_loop(run_with_timeout(awaitable, timeout))
    except TestTimeout:
        pytest.fail(f"测试超过时限 {timeout:g} 秒", pytrace=False)


class PytestTester(Tester):
    """在 pytest 下运行的 Tester：子测试失败直接成为 pytest 断言失败。"""

    async def test(self, func: Callable, note: str | None = None):  # type: ignore[override]
        """运行一个纯函数子测试，返回假值或抛异常都判为用例失败。"""
        label = note or getattr(func, "__name__", type(func).__name__)
        try:
            result = await func() if inspect.iscoroutinefunction(func) else func()
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit, GeneratorExit):
            raise
        except BaseException as error:
            raise AssertionError(f"{label}：{type(error).__name__}: {error}") from error
        if not result:
            raise AssertionError(label)
        return result


class FuncCaseItem(pytest.Item):
    """一个 ``@func_case`` 入口在 pytest 中的节点。"""

    def __init__(self, *, fn: FunctionType, **kwargs: Any):
        super().__init__(**kwargs)
        self.fn = fn

    def runtest(self) -> None:
        tester = PytestTester(self.name)
        run_test_call(self.fn, {"tester": tester}, resolve_timeout(self))

    def reportinfo(self) -> tuple[Any, int, str]:
        return self.path, 0, f"[func_case] {self.name}"


def pytest_pycollect_makeitem(collector: pytest.Collector, name: str, obj: object) -> pytest.Item | None:
    """把 ``@func_case`` 入口接管为框架节点，其余函数交回 pytest 默认收集。"""
    if not isinstance(collector, pytest.Module):
        return None
    if not isinstance(obj, FunctionType) or not getattr(obj, FUNC_CASE_ATTR, False):
        return None
    return FuncCaseItem.from_parent(collector, name=name, fn=obj)


__all__ = [
    "DEFAULT_TEST_TIMEOUT",
    "FUNC_CASE_ATTR",
    "TIMEOUT_ENV",
    "FuncCaseItem",
    "PytestTester",
    "TestTimeout",
    "close_session_loop",
    "get_session_loop",
    "prepare_runtime",
    "resolve_timeout",
    "run_in_session_loop",
    "run_test_call",
    "run_with_timeout",
]
