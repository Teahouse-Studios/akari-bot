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

    return tester
