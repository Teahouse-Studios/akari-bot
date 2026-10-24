import asyncio
import codecs
import locale
import os
import re
from collections.abc import AsyncIterator
from contextlib import aclosing
from pathlib import Path
from typing import Any

import orjson
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from bots.web.client import app, client_cleanup, get_client_ip, limiter
from core.constants import Info
from core.logger import Logger
from core.queue.contracts import ServerAPI
from .auth import verify_jwt

ROOT_DIR = Path(__file__).parent.parent.parent.parent.resolve()
GIT_TIMEOUT = 120
DEPENDENCY_TIMEOUT = 600
RESTART_WAIT_TIMEOUT = 60
RESTART_WAIT_INTERVAL = 10
LINE_SPLIT_PATTERN = re.compile(r"[\r\n]")

_update_lock = asyncio.Lock()
_restart_task: asyncio.Task | None = None
_restart_force_requested = False
_restart_force_event = asyncio.Event()
_restart_status: dict[str, Any] = {
    "pending": False,
    "force": False,
    "state": "idle",
    "active_sessions": 0,
}
_restart_status_revision = 0
_restart_status_changed = asyncio.Event()


def _set_restart_status(**updates: Any) -> None:
    global _restart_status_revision, _restart_status_changed
    _restart_status.update(updates)
    _restart_status_revision += 1
    _restart_status_changed.set()
    _restart_status_changed = asyncio.Event()


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {orjson.dumps(data).decode()}\n\n"


async def _read_force(request: Request) -> bool:
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    force = body.get("force", False)
    if not isinstance(force, bool):
        raise HTTPException(status_code=400, detail='"force" must be bool')
    return force


async def _is_git_repository() -> bool:
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            "rev-parse",
            "--is-inside-work-tree",
            cwd=ROOT_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        return False
    try:
        async with asyncio.timeout(10):
            stdout, _ = await process.communicate()
    except TimeoutError:
        return False
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    return process.returncode == 0 and stdout.strip() == b"true"


async def _stream_command(command: list[str], timeout: float) -> AsyncIterator[tuple[str, str | int]]:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=ROOT_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as e:
        yield "line", f"Failed to start command {command[0]}: {e}"
        yield "exit", -1
        return

    assert process.stdout is not None
    try:
        async with asyncio.timeout(timeout):
            decoder = codecs.getincrementaldecoder(locale.getpreferredencoding(False))(errors="replace")
            buffer = ""
            while True:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                buffer += decoder.decode(chunk)
                lines = LINE_SPLIT_PATTERN.split(buffer)
                buffer = lines.pop()
                for line in lines:
                    if line.strip():
                        yield "line", line
            buffer += decoder.decode(b"", final=True)
            if buffer.strip():
                yield "line", buffer
            returncode = await process.wait()
        yield "exit", returncode
    except TimeoutError:
        yield "line", f"Command timed out after {int(timeout)} seconds."
        yield "exit", -1
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def _update_events(force: bool, ip: str) -> AsyncIterator[str]:
    success = False
    try:
        yield _sse("start", {"force": force})

        if Info.binary_mode:
            yield _sse(
                "error",
                {"code": "binary_mode", "message": "The bot is running in binary mode and cannot be updated."},
            )
        else:
            success = True

            if not await _is_git_repository():
                yield _sse("stage", {"stage": "git", "skipped": True, "reason": "not_a_git_repository"})
            else:
                if force:
                    yield _sse("stage", {"stage": "git", "action": "reset"})
                    async with aclosing(_stream_command(["git", "reset", "--hard"], GIT_TIMEOUT)) as stream:
                        async for kind, payload in stream:
                            if kind == "line":
                                yield _sse("output", {"stage": "git", "line": payload})

                yield _sse("stage", {"stage": "git", "action": "pull"})
                git_returncode = -1
                async with aclosing(_stream_command(["git", "pull"], GIT_TIMEOUT)) as stream:
                    async for kind, payload in stream:
                        if kind == "line":
                            yield _sse("output", {"stage": "git", "line": payload})
                        else:
                            git_returncode = int(payload)
                success = git_returncode == 0
                yield _sse("stage", {"stage": "git", "action": "pull", "returncode": git_returncode})

            yield _sse("stage", {"stage": "dependencies", "tool": "uv"})
            dependency_returncode = -1
            async with aclosing(_stream_command(["uv", "sync"], DEPENDENCY_TIMEOUT)) as stream:
                async for kind, payload in stream:
                    if kind == "line":
                        yield _sse("output", {"stage": "dependencies", "line": payload})
                    else:
                        dependency_returncode = int(payload)

            tool = "uv"
            if dependency_returncode != 0:
                tool = "pip"
                yield _sse("stage", {"stage": "dependencies", "tool": "pip"})
                async with aclosing(
                    _stream_command(["pip", "install", "-r", "requirements.txt"], DEPENDENCY_TIMEOUT)
                ) as stream:
                    async for kind, payload in stream:
                        if kind == "line":
                            yield _sse("output", {"stage": "dependencies", "line": payload})
                        else:
                            dependency_returncode = int(payload)

            success = success and dependency_returncode == 0
            yield _sse("stage", {"stage": "dependencies", "tool": tool, "returncode": dependency_returncode})

        yield _sse("done", {"success": success})
        if success:
            Logger.info(f"[WebUI] {ip} updated the bot.")
        else:
            Logger.warning(f"[WebUI] {ip} failed to update the bot.")
    except Exception:
        Logger.exception(f"[WebUI] {ip} failed to update the bot.")
        yield _sse("error", {"code": "internal_error", "message": "Update failed unexpectedly."})
        yield _sse("done", {"success": False})
    finally:
        _update_lock.release()


@app.post("/api/update")
@limiter.limit("3/minute")
async def update_bot(request: Request):
    ip = get_client_ip(request)
    verify_jwt(request)
    force = await _read_force(request)

    if _update_lock.locked():
        raise HTTPException(status_code=409, detail="Update already in progress")

    await _update_lock.acquire()
    Logger.info(f"[WebUI] {ip} started updating the bot.")
    return StreamingResponse(
        _update_events(force, ip),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _wait_for_active_sessions() -> None:
    deadline = asyncio.get_running_loop().time() + RESTART_WAIT_TIMEOUT
    while not _restart_force_requested:
        try:
            active = await ServerAPI.get_active_session_count()
        except Exception:
            # 服务端不可用时无法判断会话状态，继续重启比把进程留在等待状态更可靠。
            Logger.exception("Failed to read active session count before restart; restarting anyway.")
            _set_restart_status(state="restarting", active_sessions=0)
            return
        _set_restart_status(state="waiting", active_sessions=active)
        if active <= 0:
            _set_restart_status(state="restarting")
            return
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            Logger.warning(f"Restart wait timed out with {active} active session(s), restarting anyway.")
            _set_restart_status(state="restarting", active_sessions=0)
            return
        Logger.info(f"Waiting for {active} active session(s) before restart.")
        try:
            await asyncio.wait_for(_restart_force_event.wait(), timeout=min(RESTART_WAIT_INTERVAL, remaining))
            _set_restart_status(state="restarting", active_sessions=0)
            return
        except TimeoutError:
            continue


async def restart(force: bool = False) -> None:
    _set_restart_status(
        pending=True,
        force=force,
        state="restarting" if force else "waiting",
        active_sessions=0,
    )
    if not force:
        await _wait_for_active_sessions()
    _set_restart_status(state="restarting")
    await asyncio.sleep(1)
    try:
        await client_cleanup()
    except BaseException:
        # 重启请求已经被接受，清理失败不能把进程留在半关闭状态；记录后仍交给守护进程重启。
        Logger.exception("Failed to clean up Web client before restart: ")
    os._exit(33)


def _restart_done(task: asyncio.Task) -> None:
    global _restart_task, _restart_force_requested
    if _restart_task is task:
        _restart_task = None
        _restart_force_requested = False
        _restart_force_event.clear()
        _set_restart_status(pending=False, force=False, state="idle", active_sessions=0)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        Logger.error(f"Web restart task failed: {error!r}")


def schedule_restart(force: bool = False) -> asyncio.Task:
    """Schedule at most one retained Web restart task; a force request upgrades a pending restart."""
    global _restart_task, _restart_force_requested
    if _restart_task is not None and not _restart_task.done():
        if force and not _restart_force_requested:
            _restart_force_requested = True
            _restart_force_event.set()
            _set_restart_status(force=True)
        return _restart_task

    _restart_force_requested = force
    _restart_force_event.clear()
    _set_restart_status(
        pending=True,
        force=force,
        state="restarting" if force else "waiting",
        active_sessions=0,
    )
    awaitable = restart(force)
    try:
        _restart_task = asyncio.create_task(awaitable, name="web-restart")
    except BaseException:
        awaitable.close()
        _restart_force_requested = False
        _set_restart_status(pending=False, force=False, state="idle", active_sessions=0)
        raise
    _restart_task.add_done_callback(_restart_done)
    return _restart_task


async def _restart_events() -> AsyncIterator[str]:
    seen = -1
    while True:
        event = _restart_status_changed
        revision = _restart_status_revision
        snapshot = dict(_restart_status)
        if revision != seen:
            seen = revision
            yield _sse("status", snapshot)
            if not snapshot["pending"]:
                return
        await event.wait()


@app.post("/api/restart")
@limiter.limit("3/minute")
async def restart_bot(request: Request):
    ip = get_client_ip(request)
    verify_jwt(request)
    force = await _read_force(request)
    Logger.info(f"[WebUI] {ip} restarted bot{' forcefully' if force else ''}.")
    schedule_restart(force)
    return StreamingResponse(
        _restart_events(),
        status_code=202,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
