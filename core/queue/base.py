"""Symmetric RPC runtime. Contracts own codecs; transports own delivery.

Cancellation stops local waiting only. The receiver uses the request deadline and
never retries a claimed request. Each peer has independent handlers and waiters.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import socket
import time
import traceback
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import uuid4

from core.constants import QueueAlreadyRunning
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
from core.queue.peer import (
    PeerDirectory,
    PeerIdentity,
    PeerSelector,
    ServiceRoute,
    SignalContext,
    SignalReceipt,
    SignalReport,
)

current_peer: ContextVar[type[JobQueueBase] | None] = ContextVar("rpc_current_peer", default=None)
current_request: ContextVar[RpcRequest | None] = ContextVar("rpc_current_request", default=None)
type Handler = Callable[[JsonValue], Awaitable[JsonValue]]
type SignalHandler = Callable[[SignalContext, JsonValue], Awaitable[JsonValue]]


class JobQueueBase:
    name = "Internal|" + str(uuid4())
    _auto_peer_id = True
    TASK_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
    POLL_INTERVAL_SECONDS = 0.1
    transport: RpcTransport = DatabaseTransport()
    handlers: dict[str, Handler] = {}
    signal_handlers: dict[str, list[SignalHandler]] = {}
    identity: PeerIdentity | None = None
    _pending: dict[str, asyncio.Future[RpcResponse]] = {}
    _process_tasks: set[asyncio.Task[None]] = set()
    pause_event = asyncio.Event()
    pause_event.set()
    _poll_lock = asyncio.Lock()
    _poller_task: asyncio.Task | None = None
    _ready_event = asyncio.Event()
    _registered = False
    _maintenance_active = False
    is_running = False
    _shutting_down = False
    HEARTBEAT_INTERVAL_SECONDS = 15
    RECONCILE_INTERVAL_SECONDS = 10
    _next_heartbeat = 0.0
    _next_reconcile = 0.0

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.handlers = dict(cls.handlers)
        cls.signal_handlers = {name: list(handlers) for name, handlers in cls.signal_handlers.items()}
        cls.identity = None
        cls._pending = {}
        cls._process_tasks = set()
        cls.pause_event = asyncio.Event()
        cls.pause_event.set()
        cls._poll_lock = asyncio.Lock()
        cls._poller_task = None
        cls._ready_event = asyncio.Event()
        cls._registered = False
        cls._maintenance_active = False
        cls.is_running = False
        cls._shutting_down = False
        cls._next_heartbeat = 0.0
        cls._next_reconcile = 0.0
        cls._auto_peer_id = "name" not in cls.__dict__
        if cls._auto_peer_id:
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
    def configure_peer(
        cls,
        *,
        role: str,
        service: str,
        node_id: str | None = None,
        capabilities: list[str] | tuple[str, ...] = (),
        metadata: dict | None = None,
    ) -> PeerIdentity:
        """Declare the process identity advertised through the shared registry."""
        if cls.is_running:
            raise RuntimeError("Cannot reconfigure a running JobQueue peer")
        if cls._registered:
            raise RuntimeError("Cannot reconfigure a registered JobQueue peer before stopping it")
        if not isinstance(role, str) or not role or len(role) > 32:
            raise ValueError("Peer role must be a nonempty string no longer than 32 characters")
        if not isinstance(service, str) or not service or len(service) > 128:
            raise ValueError("Peer service must be a nonempty string no longer than 128 characters")
        if any(not isinstance(capability, str) or not capability for capability in capabilities):
            raise ValueError("Peer capabilities must be nonempty strings")
        if cls._auto_peer_id:
            cls.name = "Internal|" + str(uuid4())
        if not isinstance(cls.name, str) or not cls.name or len(cls.name) > 128:
            raise ValueError("Peer ID must be a nonempty string no longer than 128 characters")
        cls._ready_event.clear()
        cls._registered = False
        cls._maintenance_active = False
        cls._shutting_down = False
        cls.pause_event.set()
        peer_metadata = {**dict(metadata or {}), "pid": os.getpid()}
        json.dumps(peer_metadata, allow_nan=False)
        resolved_node_id = node_id or socket.gethostname()[:128]
        if not isinstance(resolved_node_id, str) or not resolved_node_id or len(resolved_node_id) > 128:
            raise ValueError("Peer node ID must be a nonempty string no longer than 128 characters")
        cls.identity = PeerIdentity(
            peer_id=cls.name,
            node_id=resolved_node_id,
            role=role,
            service=service,
            capabilities=tuple(capabilities),
            metadata=peer_metadata,
        )
        from core.constants import Info

        Info.peer_id = cls.name
        Info.peer_role = role
        return cls.identity

    @classmethod
    def on_signal(cls, name: str, handler: SignalHandler | None = None):
        """Register one of any number of local subscribers for a signal name."""

        def bind(func: SignalHandler):
            cls.signal_handlers.setdefault(name, []).append(func)
            return func

        return bind(handler) if handler is not None else bind

    @classmethod
    def validate_target(cls, target: str) -> None:
        if not isinstance(target, str) or not target:
            raise RpcUnavailableError("RPC destination is missing.", target=target)

    @classmethod
    async def ensure_target_available(cls, target: str, route: ServiceRoute | None = None) -> None:
        """Optionally verify a destination against an authoritative transport directory."""

    @classmethod
    async def resolve_target(cls, target: str | ServiceRoute) -> str:
        """Resolve a logical service route from the authoritative peer directory."""
        if isinstance(target, str):
            return target
        peer = await PeerDirectory.select_route(target)
        if peer is None:
            return target.service
        cls._update_peer_cache(peer.snapshot())
        return peer.peer_id

    @classmethod
    def _request_duration(cls, timeout: float | None) -> float:
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("RPC timeout must be a positive finite duration.")
        duration = cls.TASK_TIMEOUT_SECONDS if timeout is None else min(timeout, cls.TASK_TIMEOUT_SECONDS)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("RPC timeout must be a positive finite duration.")
        return duration

    @staticmethod
    def _target_label(target: str | ServiceRoute) -> str:
        return target if isinstance(target, str) else target.service

    @classmethod
    def _request(
        cls,
        target: str,
        method: str,
        payload: JsonValue,
        timeout: float | None,
        *,
        message_kind: str = "rpc",
        correlation_id: str | None = None,
        task_id: str | None = None,
        deadline: float | None = None,
    ) -> RpcRequest:
        task_id = task_id or str(uuid4())
        try:
            cls.validate_target(target)
        except RpcError as exc:
            exc.method, exc.target, exc.task_id = method, target, task_id
            raise
        if not isinstance(method, str) or not method:
            raise ValueError("RPC method must be a nonempty string.")
        duration = cls._request_duration(timeout)
        json.dumps(payload, allow_nan=False)
        deadline = time.time() + duration if deadline is None else deadline
        return RpcRequest(
            task_id,
            target,
            method,
            payload,
            deadline,
            source_peer_id=cls.name,
            correlation_id=correlation_id,
            message_kind=message_kind,
        )

    @classmethod
    async def call(
        cls,
        target: str | ServiceRoute,
        method: str,
        payload: JsonValue,
        *,
        timeout: float | None = None,
    ) -> JsonValue:
        task_id = str(uuid4())
        deadline = time.time() + cls._request_duration(timeout)
        resolved_target = cls._target_label(target)
        future = None
        try:
            async with asyncio.timeout(max(0, deadline - time.time())):
                resolved_target = await cls.resolve_target(target)
                request = cls._request(
                    resolved_target,
                    method,
                    payload,
                    timeout,
                    task_id=task_id,
                    deadline=deadline,
                )
                future = asyncio.get_running_loop().create_future()
                cls._pending[request.task_id] = future
                await cls.ensure_target_available(
                    resolved_target,
                    target if isinstance(target, ServiceRoute) else None,
                )
                await cls.transport.send(request)
                response = await future
            return cls._decode_response(request, response)
        except RpcError as exc:
            exc.method, exc.target, exc.task_id = method, resolved_target, task_id
            raise
        except TimeoutError as exc:
            raise RpcTimeoutError(
                f"RPC {method} on {resolved_target} exceeded its deadline; remote completion is unknown.",
                method=method,
                target=resolved_target,
                task_id=task_id,
            ) from exc
        finally:
            cls._pending.pop(task_id, None)
            if future is not None and not future.done():
                future.cancel()

    @classmethod
    async def submit(
        cls,
        target: str | ServiceRoute,
        method: str,
        payload: JsonValue,
        *,
        timeout: float | None = None,
    ) -> str:
        """Return an accepted task ID; acceptance does not promise execution success."""
        task_id = str(uuid4())
        deadline = time.time() + cls._request_duration(timeout)
        resolved_target = cls._target_label(target)
        try:
            async with asyncio.timeout(max(0, deadline - time.time())):
                resolved_target = await cls.resolve_target(target)
                request = cls._request(
                    resolved_target,
                    method,
                    payload,
                    timeout,
                    task_id=task_id,
                    deadline=deadline,
                )
                await cls.ensure_target_available(
                    resolved_target,
                    target if isinstance(target, ServiceRoute) else None,
                )
                await cls.transport.send(request)
        except RpcError as exc:
            exc.method, exc.target, exc.task_id = method, resolved_target, task_id
            raise
        except TimeoutError as exc:
            raise RpcTimeoutError(
                f"RPC submission {method} exceeded its deadline; acceptance is unknown.",
                method=method,
                target=resolved_target,
                task_id=task_id,
            ) from exc
        return task_id

    @classmethod
    async def emit_signal(
        cls,
        name: str,
        payload: JsonValue,
        selector: PeerSelector | None = None,
        *,
        timeout: float | None = 30,
    ) -> SignalReceipt:
        """Fan out one signal into an independent direct delivery per ready peer."""
        event_id = str(uuid4())
        deadline = time.time() + cls._request_duration(timeout)
        try:
            async with asyncio.timeout(max(0, deadline - time.time())):
                peers = await PeerDirectory.resolve(selector)
                for peer in peers:
                    cls._update_peer_cache(peer.snapshot())
                requests = [
                    cls._request(
                        peer.peer_id,
                        name,
                        payload,
                        timeout,
                        message_kind="signal",
                        correlation_id=event_id,
                        deadline=deadline,
                    )
                    for peer in peers
                ]
                if requests:
                    await cls.transport.send_many(requests)
        except TimeoutError as exc:
            raise RpcTimeoutError(
                f"Signal submission {name} exceeded its deadline; acceptance is unknown.",
                method=name,
                target="fan-out",
                task_id=event_id,
            ) from exc
        return SignalReceipt(event_id, {peer.peer_id: request.task_id for peer, request in zip(peers, requests)})

    @classmethod
    async def gather_signal(
        cls,
        name: str,
        payload: JsonValue,
        selector: PeerSelector | None = None,
        *,
        timeout: float | None = 30,
    ) -> SignalReport:
        """Fan out a signal and collect each process instance's independent ACK."""
        event_id = str(uuid4())
        deadline = time.time() + cls._request_duration(timeout)
        peers = []
        requests = []
        futures = {}
        try:
            try:
                async with asyncio.timeout(max(0, deadline - time.time())):
                    peers = await PeerDirectory.resolve(selector)
                    for peer in peers:
                        cls._update_peer_cache(peer.snapshot())
                    requests = [
                        cls._request(
                            peer.peer_id,
                            name,
                            payload,
                            timeout,
                            message_kind="signal",
                            correlation_id=event_id,
                            deadline=deadline,
                        )
                        for peer in peers
                    ]
                    for request in requests:
                        future = asyncio.get_running_loop().create_future()
                        cls._pending[request.task_id] = future
                        futures[request.task_id] = future
                    if requests:
                        await cls.transport.send_many(requests)
            except TimeoutError as exc:
                raise RpcTimeoutError(
                    f"Signal submission {name} exceeded its deadline; acceptance is unknown.",
                    method=name,
                    target="fan-out",
                    task_id=event_id,
                ) from exc

            async def wait_one(request: RpcRequest):
                try:
                    async with asyncio.timeout(max(0, request.deadline - time.time())):
                        response = await futures[request.task_id]
                    return cls._decode_response(request, response)
                except TimeoutError:
                    return RpcTimeoutError(
                        "Signal acknowledgement exceeded its deadline.",
                        method=name,
                        target=request.target,
                        task_id=request.task_id,
                    )
                except Exception as exc:
                    return exc

            outcomes = await asyncio.gather(*(wait_one(request) for request in requests))
        finally:
            for request in requests:
                future = cls._pending.pop(request.task_id, None)
                if future is not None and not future.done():
                    future.cancel()
        results, errors = {}, {}
        for peer, outcome in zip(peers, outcomes):
            if isinstance(outcome, BaseException):
                errors[peer.peer_id] = str(outcome)
            else:
                results[peer.peer_id] = outcome
        return SignalReport(event_id, results, errors)

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
        request_token = current_request.set(request)
        try:
            if request.version != PROTOCOL_VERSION:
                raise RpcProtocolError(f"Unsupported RPC protocol version: {request.version}.")
            if not math.isfinite(request.deadline):
                raise RpcProtocolError("Invalid RPC deadline.")
            remaining = min(request.deadline - time.time(), cls.TASK_TIMEOUT_SECONDS)
            if remaining <= 0:
                raise RpcTimeoutError("Request expired before execution.")
            deadline_scope = asyncio.timeout(remaining)
            try:
                async with deadline_scope:
                    if request.message_kind == "signal":
                        value = await cls._dispatch_signal(request)
                    elif request.message_kind == "rpc":
                        handler = cls.handlers.get(request.method)
                        if handler is None:
                            raise RpcMethodNotFoundError(f"RPC method is not registered: {request.method}.")
                        value = await handler(request.payload)
                    else:
                        raise RpcProtocolError(f"Unsupported message kind: {request.message_kind}.")
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
            current_request.reset(request_token)
            current_peer.reset(peer_token)

    @classmethod
    async def _dispatch_signal(cls, request: RpcRequest) -> JsonValue:
        context = SignalContext(request.correlation_id or request.task_id, request.source_peer_id, cls.name)
        signal_payload = request.payload
        lifecycle_signals = {
            "peer.ready",
            "peer.welcome",
            "peer.maintenance",
            "peer.resumed",
            "peer.draining",
            "peer.stopped",
        }
        if request.method in lifecycle_signals and not isinstance(request.payload, dict):
            raise RpcProtocolError("Peer lifecycle signal payload must be an object.")
        if request.method in ("peer.ready", "peer.welcome"):
            peer_id = request.payload.get("peer_id")
            if not isinstance(peer_id, str) or not peer_id:
                raise RpcProtocolError("Peer lifecycle signal is missing a valid peer ID.")
            if request.source_peer_id != peer_id:
                raise RpcProtocolError("Peer lifecycle signal source does not match its announced peer ID.")
            announced = await PeerDirectory.resolve(PeerSelector.peer(peer_id))
            if not announced:
                return []
            signal_payload = announced[0].snapshot()
            cls._update_peer_cache(signal_payload)
            if request.method == "peer.ready" and request.source_peer_id and cls.identity is not None:
                records = await PeerDirectory.resolve(PeerSelector.peer(cls.name))
                if records:
                    welcome = cls._request(
                        request.source_peer_id,
                        "peer.welcome",
                        records[0].snapshot(),
                        30,
                        message_kind="signal",
                        correlation_id=context.event_id,
                    )
                    await cls.transport.send(welcome)
        elif request.method in ("peer.maintenance", "peer.draining", "peer.stopped"):
            peer_id = request.payload.get("peer_id")
            if not isinstance(peer_id, str) or not peer_id:
                raise RpcProtocolError("Peer lifecycle signal is missing a valid peer ID.")
            if request.source_peer_id != peer_id:
                raise RpcProtocolError("Peer lifecycle signal source does not match its announced peer ID.")
            state = {
                "peer.maintenance": "maintenance",
                "peer.draining": "draining",
                "peer.stopped": "stopped",
            }[request.method]
            announced = await PeerDirectory.lookup(peer_id)
            if announced is None or announced.state != state:
                return []
            signal_payload = announced.snapshot()
            cls._update_peer_cache(signal_payload)
        elif request.method == "peer.resumed":
            peer_id = request.payload.get("peer_id")
            if not isinstance(peer_id, str) or not peer_id:
                raise RpcProtocolError("Peer lifecycle signal is missing a valid peer ID.")
            if request.source_peer_id != peer_id:
                raise RpcProtocolError("Peer lifecycle signal source does not match its announced peer ID.")
            records = await PeerDirectory.resolve(PeerSelector.peer(peer_id))
            if not records:
                return []
            signal_payload = records[0].snapshot()
            cls._update_peer_cache(signal_payload, force=True)
        handlers = cls.signal_handlers.get(request.method, [])
        outcomes = await asyncio.gather(
            *(handler(context, signal_payload) for handler in handlers), return_exceptions=True
        )
        errors = [f"{type(outcome).__name__}: {outcome}" for outcome in outcomes if isinstance(outcome, BaseException)]
        if errors:
            raise RuntimeError("; ".join(errors))
        return outcomes

    @staticmethod
    def _update_peer_cache(snapshot: dict, *, force: bool = False) -> None:
        from core.alive import Alive

        peer_id = snapshot.get("peer_id")
        if not isinstance(peer_id, str) or not peer_id:
            return
        lease_until = snapshot.get("lease_until")
        if isinstance(lease_until, (int, float)):
            from datetime import UTC, datetime

            lease_until = datetime.fromtimestamp(lease_until, UTC)
        Alive.refresh_peer(
            peer_id,
            str(snapshot.get("service", "")),
            role=str(snapshot.get("role", "client")),
            state=str(snapshot.get("state", "ready")),
            capabilities=list(snapshot.get("capabilities", [])),
            metadata=dict(snapshot.get("metadata", {})),
            lease_until=lease_until,
            force=force,
        )

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
    async def _check_queue(cls, target: str | None = None, claim_new: bool = True):
        if cls._pending:
            for response in await cls.transport.responses(list(cls._pending)):
                future = cls._pending.get(response.task_id)
                if future is not None and not future.done():
                    future.set_result(response)
        if not claim_new:
            return
        targets = [cls.name]
        if target:
            targets.append(target)
        elif cls.identity is not None:
            targets.append(cls.identity.service)
        for request in await cls.transport.receive(list(dict.fromkeys(targets)), cls.name):
            task = asyncio.create_task(
                cls._process_task(request), name=f"{request.message_kind}:{request.method}:{request.task_id}"
            )
            cls._process_tasks.add(task)
            task.add_done_callback(cls._process_task_done)

    @classmethod
    async def check_job_queue(cls, target: str | None = None):
        if cls.is_running:
            raise QueueAlreadyRunning
        current = asyncio.current_task()
        cls._poller_task = current
        cls.is_running = True
        graceful_stop = False
        try:
            await cls._start_peer()
            while True:
                async with cls._poll_lock:
                    await cls._check_queue(target, claim_new=cls.pause_event.is_set())
                    await cls._maintain_peer()
                await asyncio.sleep(cls.POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            graceful_stop = True
            raise
        finally:
            if graceful_stop or cls._shutting_down:
                await cls._stop_peer()
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
    async def wait_ready(cls, timeout: float = 30) -> None:
        if cls.identity is None or cls._ready_event.is_set():
            return
        async with asyncio.timeout(timeout):
            while not cls._ready_event.is_set():
                task = cls._poller_task
                if task is not None and task.done():
                    await task
                    raise RuntimeError("JobQueue poller stopped before peer registration completed")
                await asyncio.sleep(0.01)

    @classmethod
    async def _start_peer(cls) -> None:
        if cls.identity is None:
            return
        cls._registered = True
        await PeerDirectory.register(cls.identity, "starting")
        if not await PeerDirectory.set_state(cls.name, "ready"):
            await PeerDirectory.register(cls.identity, "ready")
        records = await PeerDirectory.refresh_alive_cache()
        own = next((record for record in records if record.peer_id == cls.name), None)
        if own is not None:
            await cls.emit_signal(
                "peer.ready",
                own.snapshot(),
                PeerSelector.all().excluding(cls.name),
                timeout=30,
            )
        now = time.monotonic()
        cls._next_heartbeat = now + cls.HEARTBEAT_INTERVAL_SECONDS
        cls._next_reconcile = now + cls.RECONCILE_INTERVAL_SECONDS
        cls._ready_event.set()

    @classmethod
    async def _maintain_peer(cls) -> None:
        if cls.identity is None or cls._shutting_down or cls._maintenance_active:
            return
        now = time.monotonic()
        if now >= cls._next_heartbeat:
            if not await PeerDirectory.renew(cls.identity):
                await PeerDirectory.register(cls.identity, "ready")
            cls._next_heartbeat = now + cls.HEARTBEAT_INTERVAL_SECONDS
        if now >= cls._next_reconcile:
            await PeerDirectory.refresh_alive_cache()
            cls._next_reconcile = now + cls.RECONCILE_INTERVAL_SECONDS

    @classmethod
    async def _stop_peer(cls) -> None:
        if cls.identity is None or not cls._registered:
            return
        unregistered = False
        try:
            await PeerDirectory.set_state(cls.name, "draining")
            unregistered = await PeerDirectory.unregister(cls.name)
            if unregistered:
                record = await PeerDirectory.lookup(cls.name)
                await cls.emit_signal(
                    "peer.stopped",
                    record.snapshot() if record is not None else cls.identity.snapshot("stopped"),
                    PeerSelector.all().excluding(cls.name),
                    timeout=10,
                )
        except Exception:
            Logger.exception(f"Failed to publish peer shutdown for {cls.name}.")
        finally:
            cls._ready_event.clear()
            cls._maintenance_active = False
            from core.alive import Alive

            Alive.refresh_peer(
                cls.name,
                cls.identity.service,
                role=cls.identity.role,
                state="stopped",
                capabilities=list(cls.identity.capabilities),
                metadata=cls.identity.metadata,
            )
            if not unregistered:
                try:
                    await PeerDirectory.unregister(cls.name)
                except Exception:
                    Logger.exception(f"Failed to unregister JobQueue peer {cls.name}.")
            cls._registered = False

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
            if cls._registered:
                await cls._stop_peer()
            return
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if cls._registered:
            await cls._stop_peer()

    @classmethod
    async def begin_shutdown(cls) -> None:
        already_shutting_down = cls._shutting_down
        cls._shutting_down = True
        cls.pause_event.clear()
        async with cls._poll_lock:
            pass
        if already_shutting_down or cls.identity is None or not cls._registered:
            return
        try:
            await PeerDirectory.set_state(cls.name, "draining")
            cls._update_peer_cache(cls.identity.snapshot("draining"))
            await cls.emit_signal(
                "peer.draining",
                cls.identity.snapshot("draining"),
                PeerSelector.all().excluding(cls.name),
                timeout=10,
            )
        except Exception:
            Logger.exception(f"Failed to publish peer draining state for {cls.name}.")

    @classmethod
    @asynccontextmanager
    async def maintenance_window(cls):
        """Drain handlers while pumping responses, then exclude database polling."""
        cls.pause_event.clear()
        maintenance_started = False
        try:
            async with cls._poll_lock:
                pass
            maintenance_started = await cls._begin_maintenance()
            await cls.wait_process_tasks()
            async with cls._poll_lock:
                yield
        finally:
            if maintenance_started:
                await cls._end_maintenance()
            if not cls._shutting_down:
                cls.pause_event.set()

    @classmethod
    async def _begin_maintenance(cls) -> bool:
        if cls.identity is None or not cls._registered or cls._shutting_down or cls._maintenance_active:
            return False
        try:
            if not await PeerDirectory.set_state(
                cls.name,
                "maintenance",
                lease_seconds=PeerDirectory.MAINTENANCE_LEASE_SECONDS,
            ):
                return False
        except Exception:
            Logger.exception(f"Failed to enter peer maintenance state for {cls.name}.")
            return False
        cls._maintenance_active = True
        cls._update_peer_cache(cls.identity.snapshot("maintenance"))
        try:
            await cls.emit_signal(
                "peer.maintenance",
                cls.identity.snapshot("maintenance"),
                PeerSelector.all().excluding(cls.name),
                timeout=10,
            )
        except Exception:
            Logger.exception(f"Failed to publish peer maintenance state for {cls.name}.")
        return True

    @classmethod
    async def _end_maintenance(cls) -> None:
        try:
            if cls.identity is None or not cls._registered or cls._shutting_down:
                return
            await PeerDirectory.register(cls.identity, "ready")
            records = await PeerDirectory.resolve(PeerSelector.peer(cls.name))
            if not records:
                return
            snapshot = records[0].snapshot()
            cls._update_peer_cache(snapshot, force=True)
            await cls.emit_signal(
                "peer.resumed",
                snapshot,
                PeerSelector.all().excluding(cls.name),
                timeout=10,
            )
        except Exception:
            Logger.exception(f"Failed to publish peer resumed state for {cls.name}.")
        finally:
            cls._maintenance_active = False

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
