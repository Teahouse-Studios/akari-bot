import asyncio
import codecs
import locale
import re
from collections.abc import AsyncIterator
from contextlib import aclosing
from pathlib import Path
from typing import Any

import orjson
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from bots.web.client import app, get_client_ip, limiter
from core.constants import Info
from core.logger import Logger
from .auth import verify_jwt

ROOT_DIR = Path(__file__).parent.parent.parent.parent.resolve()
GIT_TIMEOUT = 120
DEPENDENCY_TIMEOUT = 600
LINE_SPLIT_PATTERN = re.compile(r"[\r\n]")

_update_lock = asyncio.Lock()


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {orjson.dumps(data).decode()}\n\n"


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

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    force = body.get("force", False)
    if not isinstance(force, bool):
        raise HTTPException(status_code=400, detail='"force" must be bool')

    if _update_lock.locked():
        raise HTTPException(status_code=409, detail="Update already in progress")

    await _update_lock.acquire()
    Logger.info(f"[WebUI] {ip} started updating the bot.")
    return StreamingResponse(
        _update_events(force, ip),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
