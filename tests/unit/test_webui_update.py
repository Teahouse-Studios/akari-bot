"""bots.web.api.update 单元测试 - 更新机器人接口的流式事件。"""

import asyncio
import inspect
from unittest.mock import AsyncMock, patch

import orjson
from fastapi import HTTPException

import bots.web.api.update as update_api
from core.tester import Tester, func_case


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


class _FakeProcess:
    def __init__(self, output: bytes, returncode: int = 0):
        self.stdout = asyncio.StreamReader()
        self.stdout.feed_data(output)
        self.stdout.feed_eof()
        self._returncode = returncode
        self.returncode = None
        self.killed = False

    async def wait(self):
        self.returncode = self._returncode
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def _parse_events(chunks):
    events = []
    for chunk in chunks:
        lines = chunk.strip().splitlines()
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        events.append((event, orjson.loads(data)))
    return events


def _command_factory(processes):
    remaining = list(processes)
    calls = []

    async def create(*args, **kwargs):
        calls.append((args, kwargs))
        return remaining.pop(0)

    return create, calls


def _test_sse_format():
    payload = update_api._sse("output", {"line": "a\nb"})
    return (
        payload.startswith("event: output\ndata: ")
        and payload.endswith("\n\n")
        and orjson.loads(payload.split("data: ", 1)[1].strip()) == {"line": "a\nb"}
    )


async def _test_stream_command_splits_lines():
    process = _FakeProcess(b"first line\rprogress\npartial")
    create, _ = _command_factory([process])
    with patch.object(update_api.asyncio, "create_subprocess_exec", new=create):
        events = [event async for event in update_api._stream_command(["git", "pull"], 5)]
    return events == [
        ("line", "first line"),
        ("line", "progress"),
        ("line", "partial"),
        ("exit", 0),
    ]


async def _run_update(body, processes, *, git_repo=True, binary_mode=False):
    endpoint = inspect.unwrap(update_api.update_bot)
    create, calls = _command_factory(processes)
    with (
        patch.object(update_api, "verify_jwt", lambda request: None),
        patch.object(update_api, "get_client_ip", lambda request: "test"),
        patch.object(update_api, "_is_git_repository", new=AsyncMock(return_value=git_repo)),
        patch.object(update_api.Info, "binary_mode", binary_mode),
        patch.object(update_api.asyncio, "create_subprocess_exec", new=create),
    ):
        response = await endpoint(_FakeRequest(body))
        chunks = [chunk async for chunk in response.body_iterator]
    return _parse_events(chunks), calls


async def _test_update_runs_git_and_dependencies():
    events, calls = await _run_update(
        {"force": False},
        [_FakeProcess(b"Already up to date.\n"), _FakeProcess(b"Resolved 10 packages\n")],
    )
    names = [name for name, _ in events]
    return (
        names == ["start", "stage", "output", "stage", "stage", "output", "stage", "done"]
        and [call[0] for call in calls] == [("git", "pull"), ("uv", "sync")]
        and calls[0][1]["cwd"] == update_api.ROOT_DIR
        and events[-1][1] == {"success": True}
        and not update_api._update_lock.locked()
    )


async def _test_update_force_resets_first():
    events, calls = await _run_update(
        {"force": True},
        [
            _FakeProcess(b"HEAD is now at abc123\n"),
            _FakeProcess(b"Updating abc123..def456\n"),
            _FakeProcess(b"Audited 100 packages\n"),
        ],
    )
    return (
        [call[0] for call in calls] == [("git", "reset", "--hard"), ("git", "pull"), ("uv", "sync")]
        and events[-1][1] == {"success": True}
        and not update_api._update_lock.locked()
    )


async def _test_update_falls_back_to_pip():
    events, calls = await _run_update(
        {},
        [_FakeProcess(b"uv unavailable\n", 1), _FakeProcess(b"Successfully installed\n", 0)],
        git_repo=False,
    )
    dependency_stages = [data for name, data in events if name == "stage" and data["stage"] == "dependencies"]
    return (
        [call[0] for call in calls] == [("uv", "sync"), ("pip", "install", "-r", "requirements.txt")]
        and dependency_stages[-1] == {"stage": "dependencies", "tool": "pip", "returncode": 0}
        and events[-1][1] == {"success": True}
        and not update_api._update_lock.locked()
    )


async def _test_update_skips_git_outside_repository():
    events, calls = await _run_update({}, [_FakeProcess(b"Resolved\n")], git_repo=False)
    return (
        [call[0] for call in calls] == [("uv", "sync")]
        and {"stage": "git", "skipped": True, "reason": "not_a_git_repository"} in [data for _, data in events]
        and events[-1][1] == {"success": True}
    )


async def _test_update_rejects_binary_mode():
    events, calls = await _run_update({}, [], binary_mode=True)
    return (
        [name for name, _ in events] == ["start", "error", "done"]
        and events[1][1]["code"] == "binary_mode"
        and events[-1][1] == {"success": False}
        and not calls
        and not update_api._update_lock.locked()
    )


async def _test_update_rejects_concurrent_request():
    endpoint = inspect.unwrap(update_api.update_bot)
    await update_api._update_lock.acquire()
    try:
        with (
            patch.object(update_api, "verify_jwt", lambda request: None),
            patch.object(update_api, "get_client_ip", lambda request: "test"),
        ):
            try:
                await endpoint(_FakeRequest({}))
            except HTTPException as e:
                return e.status_code == 409
            return False
    finally:
        update_api._update_lock.release()


async def _test_update_rejects_invalid_force():
    endpoint = inspect.unwrap(update_api.update_bot)
    with (
        patch.object(update_api, "verify_jwt", lambda request: None),
        patch.object(update_api, "get_client_ip", lambda request: "test"),
    ):
        try:
            await endpoint(_FakeRequest({"force": "yes"}))
        except HTTPException as e:
            return e.status_code == 400
    return False


async def _run_restart(force, active_counts=(), *, wait_interval=0.01, wait_timeout=0.1):
    order = []
    counts = list(active_counts)
    active_calls = 0

    async def sleep(_delay):
        order.append("delay")

    async def cleanup():
        order.append("cleanup")

    def exit_process(code: int):
        order.append(f"exit:{code}")

    async def active_count():
        nonlocal active_calls
        active_calls += 1
        order.append("count")
        return counts.pop(0) if counts else 0

    previous_force = update_api._restart_force_requested
    previous_status = dict(update_api._restart_status)
    previous_revision = update_api._restart_status_revision
    previous_changed = update_api._restart_status_changed
    update_api._restart_force_requested = False
    update_api._restart_force_event.clear()
    update_api._restart_status.clear()
    update_api._restart_status.update(pending=False, force=False, state="idle", active_sessions=0)
    update_api._restart_status_revision = 0
    update_api._restart_status_changed = asyncio.Event()
    try:
        with (
            patch.object(update_api.asyncio, "sleep", new=sleep),
            patch.object(update_api, "client_cleanup", new=cleanup),
            patch.object(update_api.os, "_exit", new=exit_process),
            patch.object(update_api.ServerAPI, "get_active_session_count", new=active_count),
            patch.object(update_api, "RESTART_WAIT_INTERVAL", wait_interval),
            patch.object(update_api, "RESTART_WAIT_TIMEOUT", wait_timeout),
        ):
            await update_api.restart(force)
    finally:
        update_api._restart_force_requested = previous_force
        update_api._restart_force_event.clear()
        update_api._restart_status.clear()
        update_api._restart_status.update(previous_status)
        update_api._restart_status_revision = previous_revision
        update_api._restart_status_changed = previous_changed
    return order, active_calls


async def _test_restart_waits_for_active_sessions():
    order, active_calls = await _run_restart(False, [2, 1, 0])
    return active_calls == 3 and order == ["count", "count", "count", "delay", "cleanup", "exit:33"]


async def _test_restart_force_skips_waiting():
    order, active_calls = await _run_restart(True, [1, 1])
    return active_calls == 0 and order == ["delay", "cleanup", "exit:33"]


async def _test_restart_wait_times_out():
    order, active_calls = await _run_restart(False, [1] * 100, wait_interval=0.01, wait_timeout=0.03)
    return active_calls >= 2 and order[-2:] == ["cleanup", "exit:33"]


async def _test_restart_stream_reports_active_sessions():
    previous_status = dict(update_api._restart_status)
    previous_revision = update_api._restart_status_revision
    previous_changed = update_api._restart_status_changed
    stream = None
    try:
        update_api._restart_status.clear()
        update_api._restart_status.update(pending=True, force=False, state="waiting", active_sessions=0)
        update_api._restart_status_revision = 0
        update_api._restart_status_changed = asyncio.Event()
        stream = update_api._restart_events()

        first = _parse_events([await stream.__anext__()])[0]
        update_api._set_restart_status(active_sessions=3)
        second = _parse_events([await stream.__anext__()])[0]
        update_api._set_restart_status(state="restarting", active_sessions=0)
        third = _parse_events([await stream.__anext__()])[0]
        update_api._set_restart_status(pending=False, force=False, state="idle", active_sessions=0)
        fourth = _parse_events([await stream.__anext__()])[0]
        try:
            await stream.__anext__()
        except StopAsyncIteration:
            ended = True
        else:
            ended = False
        return (
            first == ("status", {"pending": True, "force": False, "state": "waiting", "active_sessions": 0})
            and second[1]["active_sessions"] == 3
            and third[1]["state"] == "restarting"
            and fourth[1]["pending"] is False
            and fourth[1]["state"] == "idle"
            and ended
        )
    finally:
        if stream is not None:
            await stream.aclose()
        update_api._restart_status.clear()
        update_api._restart_status.update(previous_status)
        update_api._restart_status_revision = previous_revision
        update_api._restart_status_changed = previous_changed


async def _test_restart_endpoint_passes_force():
    endpoint = inspect.unwrap(update_api.restart_bot)
    forces = []
    with (
        patch.object(update_api, "verify_jwt", lambda request: None),
        patch.object(update_api, "get_client_ip", lambda request: "test"),
        patch.object(update_api, "schedule_restart", lambda force=False: forces.append(force)),
    ):
        response = await endpoint(_FakeRequest({"force": True}))
    return response.status_code == 202 and response.media_type == "text/event-stream" and forces == [True]


async def _test_restart_rejects_invalid_force():
    endpoint = inspect.unwrap(update_api.restart_bot)
    with (
        patch.object(update_api, "verify_jwt", lambda request: None),
        patch.object(update_api, "get_client_ip", lambda request: "test"),
        patch.object(update_api, "schedule_restart", lambda force=False: None),
    ):
        try:
            await endpoint(_FakeRequest({"force": 1}))
        except HTTPException as e:
            return e.status_code == 400
    return False


async def _test_schedule_restart_force_upgrades_pending_wait():
    order = []
    started = asyncio.Event()

    async def sleep(_delay):
        return None

    async def active_count():
        started.set()
        return 1

    async def cleanup():
        order.append("cleanup")

    def exit_process(code: int):
        order.append(f"exit:{code}")

    previous_task = update_api._restart_task
    previous_force = update_api._restart_force_requested
    previous_status = dict(update_api._restart_status)
    previous_revision = update_api._restart_status_revision
    previous_changed = update_api._restart_status_changed
    update_api._restart_task = None
    update_api._restart_force_requested = False
    update_api._restart_force_event.clear()
    update_api._restart_status.clear()
    update_api._restart_status.update(pending=False, force=False, state="idle", active_sessions=0)
    update_api._restart_status_revision = 0
    update_api._restart_status_changed = asyncio.Event()
    try:
        with (
            patch.object(update_api.asyncio, "sleep", new=sleep),
            patch.object(update_api, "client_cleanup", new=cleanup),
            patch.object(update_api.os, "_exit", new=exit_process),
            patch.object(update_api.ServerAPI, "get_active_session_count", new=active_count),
            patch.object(update_api, "RESTART_WAIT_INTERVAL", 5),
            patch.object(update_api, "RESTART_WAIT_TIMEOUT", 30),
        ):
            task = update_api.schedule_restart(False)
            await asyncio.wait_for(started.wait(), timeout=1)
            same_task = update_api.schedule_restart(True) is task
            upgraded = update_api._restart_force_requested
            await asyncio.wait_for(task, timeout=1)
        await asyncio.sleep(0)
        return (
            same_task
            and upgraded
            and order == ["cleanup", "exit:33"]
            and update_api._restart_task is None
            and not update_api._restart_force_requested
            and update_api._restart_status["state"] == "idle"
        )
    finally:
        task = update_api._restart_task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        update_api._restart_task = previous_task
        update_api._restart_force_requested = previous_force
        update_api._restart_force_event.clear()
        update_api._restart_status.clear()
        update_api._restart_status.update(previous_status)
        update_api._restart_status_revision = previous_revision
        update_api._restart_status_changed = previous_changed


@func_case
async def test_webui_update(tester: Tester):
    """bots.web.api: 更新机器人接口测试"""
    await tester.test(_test_sse_format, "SSE 事件格式测试")
    await tester.test(_test_stream_command_splits_lines, "命令输出分行测试")
    await tester.test(_test_update_runs_git_and_dependencies, "更新流程与流式输出测试")
    await tester.test(_test_update_force_resets_first, "强制更新重置测试")
    await tester.test(_test_update_falls_back_to_pip, "依赖安装回退测试")
    await tester.test(_test_update_skips_git_outside_repository, "非 Git 部署跳过拉取测试")
    await tester.test(_test_update_rejects_binary_mode, "二进制部署拒绝更新测试")
    await tester.test(_test_update_rejects_concurrent_request, "并发更新拦截测试")
    await tester.test(_test_update_rejects_invalid_force, "非法参数拦截测试")
    await tester.test(_test_restart_waits_for_active_sessions, "重启等待活跃会话测试")
    await tester.test(_test_restart_force_skips_waiting, "强制重启跳过等待测试")
    await tester.test(_test_restart_wait_times_out, "重启等待超时测试")
    await tester.test(_test_schedule_restart_force_upgrades_pending_wait, "强制重启升级等待任务测试")
    await tester.test(_test_restart_endpoint_passes_force, "重启接口传递参数测试")
    await tester.test(_test_restart_stream_reports_active_sessions, "重启流输出会话数测试")
    await tester.test(_test_restart_rejects_invalid_force, "重启接口非法参数拦截测试")

    return tester
