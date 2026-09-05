"""Symmetric RPC runtime. Contracts own codecs; transports own delivery.

Cancellation stops local waiting only. The receiver uses the request deadline and
never retries a claimed request. Each peer has independent handlers and waiters.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
import traceback
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import uuid4

from core.constants import QueueAlreadyRunning
from core.exports import exports
from core.logger import Logger
from core.queue.errors import (
    ERROR_TYPES,
    RpcCancelledError,
    RpcError,
    RpcMethodNotFoundError,
    RpcProtocolError,
    RpcRemoteError,
    RpcTimeoutError,
    RpcUnavailableError,
)
from core.queue.transport import (
    DatabaseTransport,
    DEFAULT_TIMEOUT_SECONDS,
    JsonValue,
    PROTOCOL_VERSION,
    RpcRequest,
    RpcResponse,
    RpcTransport,
)

current_peer: ContextVar[type[JobQueueBase] | None] = ContextVar("rpc_current_peer", default=None)
type Handler = Callable[[JsonValue], Awaitable[JsonValue]]


class JobQueueBase:
    name = "Internal|" + str(uuid4())
    TASK_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
    POLL_INTERVAL_SECONDS = 0.1
    transport: RpcTransport = DatabaseTransport()
    handlers: dict[str, Handler] = {}
    _pending: dict[str, asyncio.Future[RpcResponse]] = {}
    _process_tasks: set[asyncio.Task[None]] = set()
    pause_event = asyncio.Event()
    pause_event.set()
    _poll_lock = asyncio.Lock()
    _poller_task: asyncio.Task | None = None
    is_running = False
    _shutting_down = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.handlers = dict(cls.handlers)
        cls._pending = {}
        cls._process_tasks = set()
        cls.pause_event = asyncio.Event()
        cls.pause_event.set()
        cls._poll_lock = asyncio.Lock()
        cls._poller_task = None
        cls.is_running = False
        cls._shutting_down = False
        if "name" not in cls.__dict__:
            cls.name = "Internal|" + str(uuid4())
        if "transport" not in cls.__dict__:
            cls.transport = DatabaseTransport()

    @classmethod
    def register(cls, name: str, handler: Handler | None = None):
        """Bind a wire method directly or as a decorator; reject duplicate bindings."""

        def bind(func: Handler):
            if name in cls.handlers:
                raise ValueError(f"RPC method already registered on {cls.__name__}: {name}")
            cls.handlers[name] = func
            return func

        return bind(handler) if handler is not None else bind

    @classmethod
    def validate_target(cls, target: str) -> None:
        if not isinstance(target, str) or not target:
            raise RpcUnavailableError("RPC destination is missing.", target=target)

    @classmethod
    def _request(cls, target: str, method: str, payload: JsonValue, timeout: float | None) -> RpcRequest:
        task_id = str(uuid4())
        try:
            cls.validate_target(target)
        except RpcError as exc:
            exc.method, exc.target, exc.task_id = method, target, task_id
            raise
        if not isinstance(method, str) or not method:
            raise ValueError("RPC method must be a nonempty string.")
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("RPC timeout must be a positive finite duration.")
        duration = cls.TASK_TIMEOUT_SECONDS if timeout is None else min(timeout, cls.TASK_TIMEOUT_SECONDS)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("RPC timeout must be a positive finite duration.")
        json.dumps(payload, allow_nan=False)
        deadline = time.time() + duration
        return RpcRequest(task_id, target, method, payload, deadline)

    @classmethod
    async def call(cls, target: str, method: str, payload: JsonValue, *, timeout: float | None = None) -> JsonValue:
        request = cls._request(target, method, payload, timeout)
        future = asyncio.get_running_loop().create_future()
        cls._pending[request.task_id] = future
        try:
            async with asyncio.timeout(max(0, request.deadline - time.time())):
                await cls.transport.send(request)
                response = await future
            return cls._decode_response(request, response)
        except TimeoutError as exc:
            if isinstance(exc, RpcTimeoutError):
                raise
            raise RpcTimeoutError(
                f"RPC {method} on {target} exceeded its deadline; remote completion is unknown.",
                method=method,
                target=target,
                task_id=request.task_id,
            ) from exc
        finally:
            cls._pending.pop(request.task_id, None)
            if not future.done():
                future.cancel()

    @classmethod
    async def submit(cls, target: str, method: str, payload: JsonValue, *, timeout: float | None = None) -> str:
        """Return an accepted task ID; acceptance does not promise execution success."""
        request = cls._request(target, method, payload, timeout)
        try:
            async with asyncio.timeout(max(0, request.deadline - time.time())):
                await cls.transport.send(request)
        except TimeoutError as exc:
            raise RpcTimeoutError(
                f"RPC submission {method} exceeded its deadline; acceptance is unknown.",
                method=method,
                target=target,
                task_id=request.task_id,
            ) from exc
        return request.task_id

    @staticmethod
    def _decode_response(request: RpcRequest, response: RpcResponse) -> JsonValue:
        context = {"method": request.method, "target": request.target, "task_id": request.task_id}
        envelope = response.envelope
        if response.status == "timeout":
            raise RpcTimeoutError("The remote request expired.", **context)
        if not isinstance(envelope, dict) or envelope.get("rpc") != PROTOCOL_VERSION:
            raise RpcProtocolError("Invalid RPC response envelope.", **context)
        if response.status == "done" and "value" in envelope:
            return envelope["value"]
        error = envelope.get("error")
        if response.status != "failed" or not isinstance(error, dict):
            raise RpcProtocolError("Invalid RPC response status or error.", **context)
        error_type = ERROR_TYPES.get(error.get("code"), RpcRemoteError)
        raise error_type(
            str(error.get("message", "Remote RPC failed.")), remote_type=str(error.get("type", "")), **context
        )

    @classmethod
    async def _finish_error(cls, request: RpcRequest, error: RpcError, remote_type: str = "") -> None:
        await cls.transport.finish(
            RpcResponse(
                request.task_id,
                "timeout" if isinstance(error, RpcTimeoutError) else "failed",
                {
                    "rpc": PROTOCOL_VERSION,
                    "error": {"code": error.code, "type": remote_type or type(error).__name__, "message": str(error)},
                },
            )
        )

    @classmethod
    async def report_error(cls, method: str, details: str) -> None:
        """Override to submit reports without blocking on another RPC."""
        Logger.error(f"RPC {method} failed:\n{details}")

    @classmethod
    async def _process_task(cls, request: RpcRequest) -> None:
        peer_token = current_peer.set(cls)
        try:
            if request.version != PROTOCOL_VERSION:
                raise RpcProtocolError(f"Unsupported RPC protocol version: {request.version}.")
            if not math.isfinite(request.deadline):
                raise RpcProtocolError("Invalid RPC deadline.")
            remaining = min(request.deadline - time.time(), cls.TASK_TIMEOUT_SECONDS)
            if remaining <= 0:
                raise RpcTimeoutError("Request expired before execution.")
            handler = cls.handlers.get(request.method)
            if handler is None:
                raise RpcMethodNotFoundError(f"RPC method is not registered: {request.method}.")
            deadline_scope = asyncio.timeout(remaining)
            try:
                async with deadline_scope:
                    value = await handler(request.payload)
                    json.dumps(value, allow_nan=False)
            except TimeoutError as exc:
                if deadline_scope.expired():
                    raise RpcTimeoutError("Remote handler exceeded its deadline.") from exc
                # A handler's own TimeoutError is a remote application failure,
                # distinct from the RPC deadline expiring.
                raise
            await cls.transport.finish(RpcResponse(request.task_id, "done", {"rpc": PROTOCOL_VERSION, "value": value}))
        except asyncio.CancelledError:
            try:
                await asyncio.shield(cls._finish_error(request, RpcCancelledError("Remote handler was cancelled.")))
            except Exception:
                Logger.exception(f"Failed to record cancelled RPC {request.task_id}.")
            raise
        except RpcError as exc:
            Logger.warning(f"RPC {request.method} ({request.task_id}) failed [{exc.code}]: {exc}")
            await cls._finish_error(request, exc)
        except Exception as exc:
            details = traceback.format_exc()
            await cls._finish_error(request, RpcRemoteError(str(exc)), type(exc).__name__)
            try:
                await cls.report_error(request.method, details)
            except Exception:
                Logger.exception(f"Failed to report RPC error for {request.method}.")
        finally:
            current_peer.reset(peer_token)

    @classmethod
    def _process_task_done(cls, task: asyncio.Task[None]) -> None:
        cls._process_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            Logger.exception(f"Unhandled {cls.__name__} RPC task failure.")

    @classmethod
    async def _check_queue(cls, target_client: str | None = None, claim_new: bool = True):
        if cls._pending:
            for response in await cls.transport.responses(list(cls._pending)):
                future = cls._pending.get(response.task_id)
                if future is not None and not future.done():
                    future.set_result(response)
        if not claim_new:
            return
        targets = [cls.name]
        if target_client:
            targets.append(target_client)
        elif (bot := exports.get("Bot")) is not None and bot.Info.client_name:
            targets.append(bot.Info.client_name)
        for request in await cls.transport.receive(list(dict.fromkeys(targets))):
            task = asyncio.create_task(cls._process_task(request), name=f"rpc:{request.method}:{request.task_id}")
            cls._process_tasks.add(task)
            task.add_done_callback(cls._process_task_done)

    @classmethod
    async def check_job_queue(cls, target_client: str | None = None):
        if cls.is_running:
            raise QueueAlreadyRunning
        current = asyncio.current_task()
        cls._poller_task = current
        cls.is_running = True
        try:
            while True:
                async with cls._poll_lock:
                    await cls._check_queue(target_client, claim_new=cls.pause_event.is_set())
                await asyncio.sleep(cls.POLL_INTERVAL_SECONDS)
        finally:
            cls.is_running = False
            if cls._poller_task is current:
                cls._poller_task = None
            for task_id, future in list(cls._pending.items()):
                if not future.done():
                    future.set_result(
                        RpcResponse(
                            task_id,
                            "failed",
                            {
                                "rpc": PROTOCOL_VERSION,
                                "error": {
                                    "code": "unavailable",
                                    "type": "RpcUnavailableError",
                                    "message": "Local RPC result pump stopped.",
                                },
                            },
                        )
                    )

    @classmethod
    async def cancel_process_tasks(cls) -> None:
        current = asyncio.current_task()
        tasks = [task for task in cls._process_tasks if task is not current]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        cls._process_tasks.difference_update(tasks)

    @classmethod
    async def wait_process_tasks(cls) -> None:
        tasks = [task for task in cls._process_tasks if task is not asyncio.current_task()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @classmethod
    async def stop_job_queue(cls) -> None:
        task = cls._poller_task
        if task is None or task is asyncio.current_task():
            return
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    @classmethod
    async def begin_shutdown(cls) -> None:
        cls._shutting_down = True
        cls.pause_event.clear()
        async with cls._poll_lock:
            pass

    @classmethod
    @asynccontextmanager
    async def maintenance_window(cls):
        """Drain handlers while pumping responses, then exclude database polling."""
        cls.pause_event.clear()
        try:
            async with cls._poll_lock:
                pass
            await cls.wait_process_tasks()
            async with cls._poll_lock:
                yield
        finally:
            if not cls._shutting_down:
                cls.pause_event.set()

    @classmethod
    @asynccontextmanager
    async def shutdown_window(cls):
        """Stop new claims, cancel handlers, then exclude database polling."""
        await cls.begin_shutdown()
        try:
            await cls.cancel_process_tasks()
            async with cls._poll_lock:
                yield
        finally:
            cls._shutting_down = False
            cls.pause_event.set()
