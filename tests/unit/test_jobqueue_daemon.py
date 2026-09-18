"""JobQueue WebSocket Hub 守护进程编排测试。"""

import os
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

import bot as daemon
from core.config.jobqueue import JobQueueConfig, JobQueueSecretConfig
from core.tester import func_case, Tester


class _FakeEvent:
    def __init__(self):
        self.is_set = False

    def set(self) -> None:
        self.is_set = True

    def wait(self, timeout: float | None = None) -> bool:
        del timeout
        return self.is_set


@dataclass
class _FakeProcess:
    context: "_FakeContext"
    target: object
    args: tuple
    name: str
    daemon: bool
    pid: int = 1000
    started: bool = False
    closed: bool = False
    terminated: bool = False
    killed: bool = False

    @property
    def exitcode(self) -> int | None:
        if self.name == "jobqueue-hub" and not self.context.hub_ready:
            return 7
        if self.name == "server":
            return 0
        return None

    def start(self) -> None:
        self.started = True
        if self.name == "jobqueue-hub" and self.context.hub_ready and len(self.args) > 1:
            self.args[1].set()

    def is_alive(self) -> bool:
        return self.started and self.exitcode is None and not self.terminated and not self.killed

    def join(self, timeout: float | None = None) -> None:
        del timeout

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def close(self) -> None:
        self.closed = True


class _FakeContext:
    def __init__(self, *, hub_ready: bool = True):
        self.hub_ready = hub_ready
        self.created: list[_FakeProcess] = []

    @staticmethod
    def Event() -> _FakeEvent:
        return _FakeEvent()

    def Process(self, target, args=(), name=None, daemon=False) -> _FakeProcess:
        process = _FakeProcess(
            context=self,
            target=target,
            args=tuple(args),
            name=name or "unnamed",
            daemon=daemon,
            pid=1000 + len(self.created),
        )
        self.created.append(process)
        return process


class _FakeBotsPath:
    @staticmethod
    def iterdir():
        return iter((SimpleNamespace(name="test-platform", is_dir=lambda: True),))


async def _run_daemon_once(*, backend: str, mode: str, hub_ready: bool = True):
    context = _FakeContext(hub_ready=hub_ready)
    original_readonly = os.environ.get(daemon.CONFIG_READONLY_ENV)
    original_i18n_cache = os.environ.get("AKARI_BOT_I18N_CACHE_DIR")
    daemon.processes.clear()
    daemon.disabled_bots.clear()
    daemon.server_stop_event = None
    daemon.jobqueue_hub_stop_event = None
    try:
        with (
            patch.object(daemon.multiprocessing, "get_context", return_value=context),
            patch.object(daemon, "bots_path", _FakeBotsPath()),
            patch.object(JobQueueConfig, "jobqueue_backend", backend),
            patch.object(JobQueueConfig, "jobqueue_websocket_mode", mode),
            patch.object(JobQueueConfig, "jobqueue_websocket_url", "ws://127.0.0.1:8765/jobqueue"),
            patch.object(JobQueueConfig, "jobqueue_websocket_queue_size", 1000),
            patch.object(JobQueueConfig, "jobqueue_websocket_max_message_bytes", 1048576),
            patch.object(JobQueueConfig, "jobqueue_websocket_command_timeout", 10),
            patch.object(JobQueueSecretConfig, "jobqueue_websocket_token", ""),
        ):
            try:
                await daemon.run_bot()
            except (RuntimeError, SystemExit, TypeError, ValueError) as exc:
                return context, exc
            raise AssertionError("Daemon orchestration returned without a terminal condition")
    finally:
        daemon.processes.clear()
        daemon.disabled_bots.clear()
        daemon.server_stop_event = None
        daemon.jobqueue_hub_stop_event = None
        if original_readonly is None:
            os.environ.pop(daemon.CONFIG_READONLY_ENV, None)
        else:
            os.environ[daemon.CONFIG_READONLY_ENV] = original_readonly
        if original_i18n_cache is None:
            os.environ.pop("AKARI_BOT_I18N_CACHE_DIR", None)
        else:
            os.environ["AKARI_BOT_I18N_CACHE_DIR"] = original_i18n_cache


async def _test_embedded_hub_starts_before_peers():
    context, terminal = await _run_daemon_once(backend="websocket", mode="embedded")
    names = [process.name for process in context.created]
    return (
        isinstance(terminal, SystemExit)
        and terminal.code == 0
        and names
        == [
            "jobqueue-hub",
            "test-platform",
            "server",
        ]
    )


async def _test_external_and_database_backends_skip_hub():
    external, external_terminal = await _run_daemon_once(backend="websocket", mode="external")
    database, database_terminal = await _run_daemon_once(backend="database", mode="invalid")
    return (
        isinstance(external_terminal, SystemExit)
        and external_terminal.code == 0
        and [process.name for process in external.created] == ["test-platform", "server"]
        and isinstance(database_terminal, SystemExit)
        and database_terminal.code == 0
        and [process.name for process in database.created] == ["test-platform", "server"]
    )


async def _test_embedded_hub_start_failure_rolls_back():
    context, terminal = await _run_daemon_once(backend="websocket", mode="embedded", hub_ready=False)
    return (
        isinstance(terminal, RuntimeError)
        and [process.name for process in context.created] == ["jobqueue-hub"]
        and context.created[0].closed
    )


async def _test_invalid_websocket_mode_fails_before_starting_processes():
    context, terminal = await _run_daemon_once(backend="websocket", mode="automatic")
    return isinstance(terminal, ValueError) and not context.created


def _test_sqlite_database_backend_warns_without_changing_selection():
    with patch.object(daemon.Logger, "warning") as warning:
        warned = daemon.warn_if_database_jobqueue_uses_sqlite(" database ", " SQLITE ")
    return (
        warned
        and warning.call_count == 1
        and "database is locked" in warning.call_args.args[0]
        and 'jobqueue_backend = "websocket"' in warning.call_args.args[0]
    )


def _test_warning_is_not_emitted_for_recommended_or_non_sqlite_backends():
    with patch.object(daemon.Logger, "warning") as warning:
        results = (
            daemon.warn_if_database_jobqueue_uses_sqlite("websocket", "sqlite"),
            daemon.warn_if_database_jobqueue_uses_sqlite("database", "mysql"),
            daemon.warn_if_database_jobqueue_uses_sqlite(None, "sqlite"),
        )
    return results == (False, False, False) and warning.call_count == 0


def _test_cleanup_keeps_hub_until_last():
    context = _FakeContext()
    bot_process = context.Process(daemon.go, name="test-platform", daemon=True)
    server_process = context.Process(daemon.server_go, name="server", daemon=True)
    hub_process = context.Process(daemon.jobqueue_hub_go, name="jobqueue-hub", daemon=True)
    for process in (hub_process, server_process, bot_process):
        process.start()
    daemon.processes[:] = [hub_process, server_process, bot_process]
    server_event = _FakeEvent()
    hub_event = _FakeEvent()
    daemon.server_stop_event = server_event
    daemon.jobqueue_hub_stop_event = hub_event
    calls = []

    def record(process, graceful_event=None, graceful_timeout=10):
        calls.append((process.name, graceful_event, graceful_timeout))

    try:
        with patch.object(daemon, "terminate_process", side_effect=record):
            daemon.cleanup_processes()
        return (
            [name for name, _, _ in calls] == ["test-platform", "server", "jobqueue-hub"]
            and calls[0][1] is None
            and calls[1][1] is server_event
            and calls[2][1] is hub_event
            and daemon.processes == []
            and daemon.server_stop_event is None
            and daemon.jobqueue_hub_stop_event is None
        )
    finally:
        daemon.processes.clear()
        daemon.server_stop_event = None
        daemon.jobqueue_hub_stop_event = None


@func_case
async def test_jobqueue_daemon(tester: Tester):
    await tester.test(_test_embedded_hub_starts_before_peers, "内置 WebSocket Hub 先于 Peer 启动")
    await tester.test(_test_external_and_database_backends_skip_hub, "外部 Hub 与数据库后端不启动内置 Hub")
    await tester.test(_test_embedded_hub_start_failure_rolls_back, "内置 WebSocket Hub 启动失败回滚")
    await tester.test(
        _test_invalid_websocket_mode_fails_before_starting_processes, "非法 WebSocket Hub 模式在启动前失败"
    )
    await tester.test(_test_sqlite_database_backend_warns_without_changing_selection, "SQLite 数据库后端启动警告")
    await tester.test(_test_warning_is_not_emitted_for_recommended_or_non_sqlite_backends, "非风险后端组合不警告")
    await tester.test(_test_cleanup_keeps_hub_until_last, "守护进程按 Bot、Server、Hub 顺序关闭")
    return tester
