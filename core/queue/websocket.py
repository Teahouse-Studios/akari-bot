"""WebSocket JobQueue 后端及独立 Hub 实现。"""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import math
import socket
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import orjson
import httpx
import uvicorn
from fastapi import FastAPI, WebSocket
from httpx_ws import AsyncWebSocketSession, WebSocketDisconnect, aconnect_ws

from .errors import RpcProtocolError, RpcTimeoutError, RpcUnavailableError
from .peer import PeerIdentity, PeerRecord, PeerRegistryBase, PeerSelector, PeerState
from .transport import BatchSendResult, PROTOCOL_VERSION, RpcRequest, RpcResponse


_PEER_STATES = frozenset({"starting", "ready", "maintenance", "draining", "stopped"})


class WebSocketBackendError(RpcUnavailableError):
    """WebSocket JobQueue 连接或远端命令失败。"""


class WebSocketProtocolError(RpcProtocolError):
    """WebSocket JobQueue 帧不符合协议。"""


class WebSocketCommandTimeout(RpcTimeoutError):
    """控制命令的处理结果未知。"""


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class WebSocketSettings:
    mode: str = "embedded"
    url: str = "ws://127.0.0.1:8765/jobqueue"
    token: str = ""
    queue_size: int = 1000
    max_message_bytes: int = 1048576
    command_timeout: float = 10
    heartbeat_seconds: float = 15

    def __post_init__(self) -> None:
        if not isinstance(self.mode, str):
            raise TypeError("JobQueue WebSocket mode must be a string")
        mode = self.mode.strip().lower()
        if mode not in ("embedded", "external"):
            raise ValueError("JobQueue WebSocket mode must be embedded or external")
        if not isinstance(self.url, str):
            raise TypeError("JobQueue WebSocket URL must be a string")
        url = self.url.strip()
        try:
            parsed = urlparse(url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("JobQueue WebSocket URL contains an invalid host or port") from exc
        if parsed.scheme not in ("ws", "wss") or not parsed.hostname:
            raise ValueError("JobQueue WebSocket URL must use ws or wss and include a host")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("JobQueue WebSocket URL must not contain credentials")
        if parsed.fragment:
            raise ValueError("JobQueue WebSocket URL must not contain a fragment")
        if port is not None and not 0 <= port <= 65535:
            raise ValueError("JobQueue WebSocket URL port must be between 0 and 65535")
        if not isinstance(self.token, str):
            raise TypeError("JobQueue WebSocket token must be a string")
        for field_name in ("queue_size", "max_message_bytes"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"JobQueue WebSocket {field_name} must be a positive integer")
        for field_name in ("command_timeout", "heartbeat_seconds"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"JobQueue WebSocket {field_name} must be a positive finite duration")
        if not self.token and not _is_loopback(parsed.hostname):
            raise ValueError("A JobQueue WebSocket token is required for non-loopback connections")
        if not _is_loopback(parsed.hostname) and parsed.scheme != "wss":
            raise ValueError("Remote JobQueue WebSocket connections must use wss")
        if mode == "embedded" and not _is_loopback(parsed.hostname):
            raise ValueError("Embedded JobQueue WebSocket Hub URLs must use a loopback host")
        if mode == "embedded" and parsed.scheme != "ws":
            raise ValueError("Embedded JobQueue WebSocket Hub URLs must use ws; terminate TLS at an external Hub")
        if not parsed.path:
            parsed = parsed._replace(path="/jobqueue")
            url = parsed.geturl()
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "url", url)

    @property
    def embedded(self) -> bool:
        return self.mode == "embedded"

    @property
    def bind_host(self) -> str:
        host = urlparse(self.url).hostname
        assert host is not None
        return host

    @property
    def bind_port(self) -> int:
        parsed = urlparse(self.url)
        port = parsed.port
        return port if port is not None else (443 if parsed.scheme == "wss" else 80)

    @property
    def path(self) -> str:
        return urlparse(self.url).path or "/jobqueue"

    @classmethod
    def from_config(cls) -> "WebSocketSettings":
        from core.config.jobqueue import JobQueueConfig, JobQueueSecretConfig

        settings = cls(
            mode=JobQueueConfig.jobqueue_websocket_mode,
            url=JobQueueConfig.jobqueue_websocket_url,
            token=JobQueueSecretConfig.jobqueue_websocket_token,
            queue_size=JobQueueConfig.jobqueue_websocket_queue_size,
            max_message_bytes=JobQueueConfig.jobqueue_websocket_max_message_bytes,
            command_timeout=JobQueueConfig.jobqueue_websocket_command_timeout,
        )
        if settings.bind_port == 0:
            raise ValueError("Configured JobQueue WebSocket URL port must be between 1 and 65535")
        return settings


def _identity_to_wire(identity: PeerIdentity) -> dict[str, Any]:
    return {
        "peer_id": identity.peer_id,
        "node_id": identity.node_id,
        "role": identity.role,
        "service": identity.service,
        "capabilities": list(identity.capabilities),
        "metadata": identity.metadata,
    }


def _identity_from_wire(value: Any) -> PeerIdentity:
    if not isinstance(value, dict):
        raise WebSocketProtocolError("Peer identity must be an object")
    peer_id = value.get("peer_id")
    node_id = value.get("node_id")
    role = value.get("role")
    service = value.get("service")
    capabilities = value.get("capabilities", [])
    metadata = value.get("metadata", {})
    if not isinstance(peer_id, str) or not peer_id or len(peer_id) > 128:
        raise WebSocketProtocolError("Peer identity contains an invalid peer ID")
    if node_id is not None and (not isinstance(node_id, str) or not node_id or len(node_id) > 128):
        raise WebSocketProtocolError("Peer identity contains an invalid node ID")
    if not isinstance(role, str) or not role or len(role) > 32:
        raise WebSocketProtocolError("Peer identity contains an invalid role")
    if not isinstance(service, str) or not service or len(service) > 128:
        raise WebSocketProtocolError("Peer identity contains an invalid service")
    if not isinstance(capabilities, list) or any(not isinstance(item, str) or not item for item in capabilities):
        raise WebSocketProtocolError("Peer identity contains invalid capabilities")
    if not isinstance(metadata, dict):
        raise WebSocketProtocolError("Peer identity metadata must be an object")
    try:
        orjson.dumps(metadata)
    except (TypeError, ValueError) as exc:
        raise WebSocketProtocolError("Peer identity metadata must be JSON serializable") from exc
    return PeerIdentity(peer_id, role, service, node_id, tuple(capabilities), metadata)


def _record_to_wire(record: PeerRecord) -> dict[str, Any]:
    return record.snapshot()


def _record_from_wire(value: Any) -> PeerRecord:
    if not isinstance(value, dict):
        raise WebSocketProtocolError("Peer record must be an object")
    identity = _identity_from_wire(value)
    state = value.get("state")
    lease_until = value.get("lease_until")
    if state not in _PEER_STATES:
        raise WebSocketProtocolError("Peer record contains an invalid state")
    if isinstance(lease_until, bool) or not isinstance(lease_until, (int, float)) or not math.isfinite(lease_until):
        raise WebSocketProtocolError("Peer record contains an invalid lease timestamp")
    return PeerRecord(
        identity.peer_id,
        identity.node_id,
        identity.role,
        identity.service,
        state,
        identity.capabilities,
        identity.metadata,
        datetime.fromtimestamp(lease_until, UTC),
    )


def _selector_to_wire(selector: PeerSelector) -> dict[str, list[str]]:
    return {
        "peer_ids": list(selector.peer_ids),
        "node_ids": list(selector.node_ids),
        "roles": list(selector.roles),
        "services": list(selector.services),
        "capabilities": list(selector.capabilities),
        "exclude_peer_ids": list(selector.exclude_peer_ids),
    }


def _selector_from_wire(value: Any) -> PeerSelector:
    if not isinstance(value, dict):
        raise WebSocketProtocolError("Peer selector must be an object")
    fields = {}
    for name in ("peer_ids", "node_ids", "roles", "services", "capabilities", "exclude_peer_ids"):
        item = value.get(name, [])
        if not isinstance(item, list):
            raise WebSocketProtocolError(f"Peer selector {name} must be an array")
        fields[name] = tuple(item)
    try:
        return PeerSelector(**fields)
    except (TypeError, ValueError) as exc:
        raise WebSocketProtocolError(str(exc)) from exc


def _request_to_wire(request: RpcRequest) -> dict[str, Any]:
    return {
        "task_id": request.task_id,
        "target": request.target,
        "method": request.method,
        "payload": request.payload,
        "deadline": request.deadline,
        "version": request.version,
        "source_peer_id": request.source_peer_id,
        "correlation_id": request.correlation_id,
        "message_kind": request.message_kind,
        "expects_response": request.expects_response,
    }


def _request_from_wire(value: Any) -> RpcRequest:
    if not isinstance(value, dict):
        raise WebSocketProtocolError("RPC request must be an object")
    task_id = value.get("task_id")
    target = value.get("target")
    method = value.get("method")
    deadline = value.get("deadline")
    version = value.get("version")
    source_peer_id = value.get("source_peer_id")
    correlation_id = value.get("correlation_id")
    message_kind = value.get("message_kind")
    expects_response = value.get("expects_response")
    if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
        raise WebSocketProtocolError("RPC request contains an invalid task ID")
    if not isinstance(target, str) or not target or len(target) > 512:
        raise WebSocketProtocolError("RPC request contains an invalid target")
    if not isinstance(method, str) or not method or len(method) > 512:
        raise WebSocketProtocolError("RPC request contains an invalid method")
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline):
        raise WebSocketProtocolError("RPC request contains an invalid deadline")
    if isinstance(version, bool) or not isinstance(version, int):
        raise WebSocketProtocolError("RPC request contains an invalid protocol version")
    if source_peer_id is not None and (not isinstance(source_peer_id, str) or not source_peer_id):
        raise WebSocketProtocolError("RPC request contains an invalid source peer ID")
    if correlation_id is not None and (not isinstance(correlation_id, str) or not correlation_id):
        raise WebSocketProtocolError("RPC request contains an invalid correlation ID")
    if message_kind not in ("rpc", "signal") or not isinstance(expects_response, bool):
        raise WebSocketProtocolError("RPC request contains invalid delivery options")
    try:
        orjson.dumps(value.get("payload"))
    except (TypeError, ValueError) as exc:
        raise WebSocketProtocolError("RPC request payload must be JSON serializable") from exc
    return RpcRequest(
        task_id,
        target,
        method,
        value.get("payload"),
        float(deadline),
        version,
        source_peer_id,
        correlation_id,
        message_kind,
        expects_response,
    )


def _response_to_wire(response: RpcResponse) -> dict[str, Any]:
    return {"task_id": response.task_id, "status": response.status, "envelope": response.envelope}


def _response_from_wire(value: Any) -> RpcResponse:
    if not isinstance(value, dict):
        raise WebSocketProtocolError("RPC response must be an object")
    task_id = value.get("task_id")
    status = value.get("status")
    if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
        raise WebSocketProtocolError("RPC response contains an invalid task ID")
    if status not in ("done", "failed", "timeout"):
        raise WebSocketProtocolError("RPC response contains an invalid status")
    try:
        orjson.dumps(value.get("envelope"))
    except (TypeError, ValueError) as exc:
        raise WebSocketProtocolError("RPC response envelope must be JSON serializable") from exc
    return RpcResponse(task_id, status, value.get("envelope"))


def _encode_frame(frame: dict[str, Any], max_bytes: int) -> bytes:
    try:
        payload = orjson.dumps(frame)
    except (TypeError, ValueError) as exc:
        raise WebSocketProtocolError("WebSocket frame must be JSON serializable") from exc
    if len(payload) > max_bytes:
        raise WebSocketProtocolError(f"WebSocket frame exceeds the {max_bytes}-byte limit")
    return payload


def _decode_frame(data: bytes | str, max_bytes: int) -> dict[str, Any]:
    payload = data.encode() if isinstance(data, str) else data
    if len(payload) > max_bytes:
        raise WebSocketProtocolError(f"WebSocket frame exceeds the {max_bytes}-byte limit")
    try:
        frame = orjson.loads(payload)
    except orjson.JSONDecodeError as exc:
        raise WebSocketProtocolError("WebSocket frame is not valid JSON") from exc
    if not isinstance(frame, dict) or not isinstance(frame.get("type"), str):
        raise WebSocketProtocolError("WebSocket frame must be an object with a type")
    return frame


@dataclass
class _HubDelivery:
    request: RpcRequest
    source_peer_id: str
    target_peer_id: str


@dataclass
class _HubConnection:
    peer_id: str
    websocket: WebSocket
    outbound: asyncio.PriorityQueue[tuple[int, int, bytes]]
    delivery_limit: int
    sequence: int = 0
    delivery_pending: int = 0
    sender_task: asyncio.Task[None] | None = None

    def enqueue(self, payload: bytes, *, control: bool) -> bool:
        if not control and self.delivery_pending >= self.delivery_limit:
            return False
        try:
            self.outbound.put_nowait((0 if control else 1, self.sequence, payload))
        except asyncio.QueueFull:
            return False
        self.sequence += 1
        if not control:
            self.delivery_pending += 1
        return True


class WebSocketHub:
    """维护连接、Peer 拓扑以及非持久化投递状态的独立 Hub。"""

    LEASE_SECONDS = 45
    MAINTENANCE_LEASE_SECONDS = 600
    STOPPED_RETENTION_SECONDS = 86400

    def __init__(self, settings: WebSocketSettings):
        self.settings = settings
        self.connections: dict[str, _HubConnection] = {}
        self.peers: dict[str, PeerRecord] = {}
        self.deliveries: dict[str, _HubDelivery] = {}
        self._route_cursors: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self.app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        self.app.add_api_websocket_route(settings.path, self._handle_websocket)
        self._server: uvicorn.Server | None = None
        self._server_task: asyncio.Task[None] | None = None
        self._listen_socket: socket.socket | None = None
        self._expiry_task: asyncio.Task[None] | None = None
        self._closing = False
        self.bound_port = settings.bind_port

    @property
    def url(self) -> str:
        host = self.settings.bind_host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"ws://{host}:{self.bound_port}{self.settings.path}"

    async def start(self) -> None:
        if self._server_task is not None:
            raise RuntimeError("WebSocket JobQueue Hub is already running")
        self._closing = False
        address = socket.getaddrinfo(
            self.settings.bind_host,
            self.settings.bind_port,
            type=socket.SOCK_STREAM,
            flags=socket.AI_PASSIVE,
        )[0]
        listen_socket = socket.socket(address[0], address[1], address[2])
        self._listen_socket = listen_socket
        try:
            listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_socket.bind(address[4])
            listen_socket.listen(self.settings.queue_size)
            listen_socket.setblocking(False)
            self.bound_port = int(listen_socket.getsockname()[1])
            config = uvicorn.Config(
                self.app,
                host=self.settings.bind_host,
                port=self.bound_port,
                lifespan="off",
                access_log=False,
                log_level="warning",
                ws_max_size=self.settings.max_message_bytes,
            )
            self._server = uvicorn.Server(config)
            self._server.install_signal_handlers = lambda: None
            self._server_task = asyncio.create_task(
                self._server.serve(sockets=[listen_socket]), name="jobqueue-websocket-hub-server"
            )
            async with asyncio.timeout(self.settings.command_timeout):
                while not self._server.started:
                    if self._server_task.done():
                        await self._server_task
                        raise RuntimeError("WebSocket JobQueue Hub stopped during startup")
                    await asyncio.sleep(0.01)
            self._expiry_task = asyncio.create_task(self._expiry_loop(), name="jobqueue-websocket-hub-expiry")
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        self._closing = True
        server = self._server
        if server is not None:
            server.should_exit = True
        expiry_task = self._expiry_task
        self._expiry_task = None
        if expiry_task is not None:
            expiry_task.cancel()
            await asyncio.gather(expiry_task, return_exceptions=True)
        async with self._lock:
            connections = list(self.connections.values())
            self.connections.clear()
            self.peers.clear()
            self.deliveries.clear()
            self._route_cursors.clear()
        for connection in connections:
            try:
                await connection.websocket.close(code=1001, reason="Hub shutting down")
            except RuntimeError:
                pass
            if connection.sender_task is not None:
                connection.sender_task.cancel()
        await asyncio.gather(
            *(connection.sender_task for connection in connections if connection.sender_task is not None),
            return_exceptions=True,
        )
        server_task = self._server_task
        self._server = None
        self._server_task = None
        if server_task is not None and server_task is not asyncio.current_task():
            try:
                async with asyncio.timeout(self.settings.command_timeout):
                    await server_task
            except TimeoutError:
                if server is not None:
                    server.force_exit = True
                server_task.cancel()
                await asyncio.gather(server_task, return_exceptions=True)
        listen_socket = self._listen_socket
        self._listen_socket = None
        if listen_socket is not None:
            listen_socket.close()

    async def _expiry_loop(self) -> None:
        while True:
            await asyncio.sleep(min(5, self.LEASE_SECONDS / 3))
            async with self._lock:
                self._expire_locked()

    def _expire_locked(self) -> list[str]:
        now = datetime.now(UTC)
        expired = []
        for peer_id, record in list(self.peers.items()):
            if record.state in ("starting", "ready", "maintenance", "draining") and record.lease_until <= now:
                stopped = replace(record, state="stopped", lease_until=now)
                self.peers[peer_id] = stopped
                self._fail_target_deliveries_locked(peer_id, "Target process lease expired.")
                self._broadcast_peer_state_locked(stopped)
                expired.append(peer_id)
        retention = now - timedelta(seconds=self.STOPPED_RETENTION_SECONDS)
        for peer_id, record in list(self.peers.items()):
            if record.state == "stopped" and record.lease_until < retention:
                del self.peers[peer_id]
        self._expire_deliveries_locked(now.timestamp())
        return expired

    def _expire_deliveries_locked(self, now: float) -> None:
        envelope = {
            "rpc": PROTOCOL_VERSION,
            "error": {
                "code": "timeout",
                "type": "RpcTimeoutError",
                "message": "Request expired before completion.",
            },
        }
        for task_id, delivery in list(self.deliveries.items()):
            if delivery.request.deadline > now:
                continue
            del self.deliveries[task_id]
            if not delivery.request.expects_response:
                continue
            source = self.connections.get(delivery.source_peer_id)
            if source is not None and not self._enqueue_frame_locked(
                source,
                {"type": "response", "response": _response_to_wire(RpcResponse(task_id, "timeout", envelope))},
            ):
                self._close_overloaded_connection(source)

    async def _sender(self, connection: _HubConnection) -> None:
        try:
            while True:
                priority, _, payload = await connection.outbound.get()
                if priority == 1:
                    connection.delivery_pending -= 1
                await connection.websocket.send_bytes(payload)
        except asyncio.CancelledError:
            raise
        except BaseException:
            try:
                await connection.websocket.close(code=1011, reason="WebSocket send failed")
            except RuntimeError:
                pass

    def _enqueue_frame_locked(self, connection: _HubConnection, frame: dict[str, Any], *, control: bool = True) -> bool:
        try:
            payload = _encode_frame(frame, self.settings.max_message_bytes)
        except WebSocketProtocolError:
            return False
        return connection.enqueue(payload, control=control)

    def _broadcast_peer_state_locked(self, record: PeerRecord) -> None:
        frame = {"type": "peer_state", "peer": _record_to_wire(record)}
        for connection in self.connections.values():
            self._enqueue_frame_locked(connection, frame)

    @staticmethod
    def _close_overloaded_connection(connection: _HubConnection) -> None:
        async def close() -> None:
            try:
                await connection.websocket.close(code=1013, reason="Outbound control queue is full")
            except RuntimeError:
                pass

        asyncio.create_task(close(), name=f"jobqueue-websocket-overload:{connection.peer_id}")

    def _fail_target_deliveries_locked(self, peer_id: str, message: str) -> None:
        envelope = {
            "rpc": PROTOCOL_VERSION,
            "error": {"code": "unavailable", "type": "RpcUnavailableError", "message": message},
        }
        for task_id, delivery in list(self.deliveries.items()):
            if delivery.target_peer_id != peer_id:
                continue
            del self.deliveries[task_id]
            if not delivery.request.expects_response:
                continue
            source = self.connections.get(delivery.source_peer_id)
            if source is not None:
                queued = self._enqueue_frame_locked(
                    source,
                    {"type": "response", "response": _response_to_wire(RpcResponse(task_id, "failed", envelope))},
                )
                if not queued:
                    self._close_overloaded_connection(source)

    def _disconnect_locked(self, connection: _HubConnection) -> None:
        if self.connections.get(connection.peer_id) is not connection:
            return
        del self.connections[connection.peer_id]
        record = self.peers.get(connection.peer_id)
        if record is not None and record.state != "stopped":
            record = replace(record, state="stopped", lease_until=datetime.now(UTC))
            self.peers[connection.peer_id] = record
            self._broadcast_peer_state_locked(record)
        self._fail_target_deliveries_locked(connection.peer_id, "Target process disconnected.")
        for task_id, delivery in list(self.deliveries.items()):
            if delivery.source_peer_id == connection.peer_id:
                del self.deliveries[task_id]

    @staticmethod
    async def _receive_payload(websocket: WebSocket) -> bytes | str:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(int(message.get("code", 1000)), str(message.get("reason", "")))
        if message["type"] != "websocket.receive":
            raise WebSocketProtocolError("Expected a WebSocket data frame")
        if message.get("bytes") is not None:
            return message["bytes"]
        if message.get("text") is not None:
            return message["text"]
        raise WebSocketProtocolError("Received an empty WebSocket data frame")

    async def _handle_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        if self._closing:
            await websocket.close(code=1012, reason="Hub is shutting down")
            return
        connection = None
        try:
            payload = await asyncio.wait_for(self._receive_payload(websocket), timeout=self.settings.command_timeout)
            hello = _decode_frame(payload, self.settings.max_message_bytes)
            if hello.get("type") != "hello" or hello.get("protocol") != PROTOCOL_VERSION:
                raise WebSocketProtocolError("Unsupported JobQueue WebSocket handshake")
            provided_token = hello.get("token", "")
            if not isinstance(provided_token, str) or not hmac.compare_digest(provided_token, self.settings.token):
                await websocket.close(code=1008, reason="Authentication failed")
                return
            identity = _identity_from_wire(hello.get("identity"))
            shutting_down = False
            async with self._lock:
                if self._closing:
                    shutting_down = True
                elif identity.peer_id in self.connections:
                    await websocket.close(code=1008, reason="Peer ID is already connected")
                    return
                else:
                    connection = _HubConnection(
                        identity.peer_id,
                        websocket,
                        asyncio.PriorityQueue(
                            maxsize=self.settings.queue_size + max(16, self.settings.queue_size // 10)
                        ),
                        self.settings.queue_size,
                    )
                    self.connections[identity.peer_id] = connection
            if shutting_down:
                await websocket.close(code=1012, reason="Hub is shutting down")
                return
            await websocket.send_bytes(
                _encode_frame(
                    {"type": "welcome", "protocol": PROTOCOL_VERSION, "peer_id": identity.peer_id},
                    self.settings.max_message_bytes,
                )
            )
            connection.sender_task = asyncio.create_task(
                self._sender(connection), name=f"jobqueue-websocket-send:{identity.peer_id}"
            )
            while True:
                try:
                    frame = _decode_frame(await self._receive_payload(websocket), self.settings.max_message_bytes)
                    if frame.get("type") == "command":
                        await self._handle_command(connection, frame)
                    elif frame.get("type") == "response":
                        await self._handle_response(connection, frame)
                    else:
                        raise WebSocketProtocolError("Unsupported JobQueue WebSocket frame type")
                except WebSocketProtocolError as exc:
                    async with self._lock:
                        if not self._enqueue_frame_locked(connection, {"type": "error", "message": str(exc)}):
                            break
        except WebSocketDisconnect:
            pass
        except (TimeoutError, WebSocketProtocolError):
            try:
                await websocket.close(code=1002, reason="Invalid JobQueue protocol")
            except RuntimeError:
                pass
        finally:
            if connection is not None:
                async with self._lock:
                    self._disconnect_locked(connection)
                if connection.sender_task is not None:
                    connection.sender_task.cancel()
                    await asyncio.gather(connection.sender_task, return_exceptions=True)

    async def _handle_command(self, connection: _HubConnection, frame: dict[str, Any]) -> None:
        command_id = frame.get("id")
        operation = frame.get("op")
        if not isinstance(command_id, str) or not command_id or not isinstance(operation, str):
            raise WebSocketProtocolError("JobQueue command requires a valid ID and operation")
        try:
            async with self._lock:
                result = self._execute_command_locked(connection, operation, frame)
            response = {"type": "command_result", "id": command_id, "ok": True, "result": result}
        except (WebSocketProtocolError, ValueError, TypeError) as exc:
            response = {"type": "command_result", "id": command_id, "ok": False, "error": str(exc)}
        async with self._lock:
            if not self._enqueue_frame_locked(connection, response):
                await connection.websocket.close(code=1013, reason="Outbound queue is full")

    def _execute_command_locked(self, connection: _HubConnection, operation: str, frame: dict[str, Any]) -> Any:
        self._expire_locked()
        if operation in ("register", "renew"):
            identity = _identity_from_wire(frame.get("identity"))
            if identity.peer_id != connection.peer_id:
                raise WebSocketProtocolError("A connection may only register its authenticated peer ID")
            current = self.peers.get(identity.peer_id)
            if operation == "renew" and (current is None or current.state not in ("starting", "ready")):
                return False
            state = frame.get("state", "starting") if operation == "register" else "ready"
            if state not in _PEER_STATES:
                raise WebSocketProtocolError("Peer registration contains an invalid state")
            record = PeerRecord(
                identity.peer_id,
                identity.node_id,
                identity.role,
                identity.service,
                state,
                identity.capabilities,
                identity.metadata,
                datetime.now(UTC) + timedelta(seconds=self.LEASE_SECONDS),
            )
            self.peers[identity.peer_id] = record
            if operation == "register":
                self._broadcast_peer_state_locked(record)
            return _record_to_wire(record) if operation == "register" else True
        if operation == "set_state":
            peer_id = frame.get("peer_id")
            state = frame.get("state")
            lease_seconds = frame.get("lease_seconds")
            if peer_id != connection.peer_id or state not in _PEER_STATES:
                raise WebSocketProtocolError("A connection may only update its own valid peer state")
            current = self.peers.get(peer_id)
            if current is None:
                return False
            if lease_seconds is None:
                lease_seconds = self.LEASE_SECONDS
            if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds <= 0:
                raise WebSocketProtocolError("Peer state lease must be a positive integer")
            record = replace(
                current,
                state=state,
                lease_until=datetime.now(UTC) + timedelta(seconds=lease_seconds),
            )
            self.peers[peer_id] = record
            self._broadcast_peer_state_locked(record)
            return True
        if operation == "unregister":
            peer_id = frame.get("peer_id")
            if peer_id != connection.peer_id:
                raise WebSocketProtocolError("A connection may only unregister itself")
            current = self.peers.get(peer_id)
            if current is None:
                return False
            record = replace(current, state="stopped", lease_until=datetime.now(UTC))
            self.peers[peer_id] = record
            self._fail_target_deliveries_locked(peer_id, "Target process stopped before completing the request.")
            self._broadcast_peer_state_locked(record)
            return True
        if operation == "lookup":
            peer_id = frame.get("peer_id")
            if not isinstance(peer_id, str) or not peer_id:
                raise WebSocketProtocolError("Peer lookup requires a valid peer ID")
            record = self.peers.get(peer_id)
            return _record_to_wire(record) if record is not None else None
        if operation == "resolve":
            selector = _selector_from_wire(frame.get("selector"))
            return [_record_to_wire(record) for record in self._resolve_locked(selector)]
        if operation == "expire":
            return self._expire_locked()
        if operation == "send_many":
            values = frame.get("requests")
            if not isinstance(values, list):
                raise WebSocketProtocolError("Batch delivery requires a request array")
            accepted: list[str] = []
            rejected: dict[str, str] = {}
            seen: set[str] = set()
            parsed: list[RpcRequest] = []
            duplicate_ids: set[str] = set()
            for value in values:
                request = _request_from_wire(value)
                if request.task_id in seen:
                    duplicate_ids.add(request.task_id)
                seen.add(request.task_id)
                parsed.append(request)
            for request in parsed:
                if request.task_id in duplicate_ids or request.task_id in self.deliveries:
                    rejected[request.task_id] = "Duplicate JobQueue task ID."
                    continue
                request = replace(request, source_peer_id=connection.peer_id)
                target = self._select_target_locked(request.target)
                if target is None:
                    rejected[request.task_id] = "No ready WebSocket peer is available for this target."
                    continue
                target_connection = self.connections.get(target.peer_id)
                if target_connection is None:
                    rejected[request.task_id] = "The selected WebSocket peer is disconnected."
                    continue
                delivery = _HubDelivery(request, connection.peer_id, target.peer_id)
                self.deliveries[request.task_id] = delivery
                if not self._enqueue_frame_locked(
                    target_connection,
                    {"type": "request", "request": _request_to_wire(replace(request, target=target.peer_id))},
                    control=False,
                ):
                    del self.deliveries[request.task_id]
                    rejected[request.task_id] = "The target WebSocket peer is applying backpressure."
                    continue
                accepted.append(request.task_id)
            return {"accepted": accepted, "rejected": rejected, "unknown": []}
        if operation == "abandon":
            task_ids = frame.get("task_ids")
            if not isinstance(task_ids, list) or any(not isinstance(task_id, str) for task_id in task_ids):
                raise WebSocketProtocolError("Abandon requires an array of task IDs")
            for task_id in task_ids:
                delivery = self.deliveries.get(task_id)
                if delivery is not None and delivery.source_peer_id == connection.peer_id:
                    del self.deliveries[task_id]
            return True
        raise WebSocketProtocolError(f"Unsupported JobQueue command: {operation}")

    def _resolve_locked(self, selector: PeerSelector) -> list[PeerRecord]:
        now = datetime.now(UTC)
        required_capabilities = set(selector.capabilities)
        records = [
            record
            for record in self.peers.values()
            if record.state == "ready"
            and record.lease_until > now
            and record.peer_id in self.connections
            and (not selector.peer_ids or record.peer_id in selector.peer_ids)
            and (not selector.node_ids or record.node_id in selector.node_ids)
            and (not selector.roles or record.role in selector.roles)
            and (not selector.services or record.service in selector.services)
            and record.peer_id not in selector.exclude_peer_ids
            and (not required_capabilities or required_capabilities.issubset(record.capabilities))
        ]
        return sorted(records, key=lambda record: record.peer_id)

    def _select_target_locked(self, target: str) -> PeerRecord | None:
        direct = self.peers.get(target)
        now = datetime.now(UTC)
        if (
            direct is not None
            and direct.state == "ready"
            and direct.lease_until > now
            and direct.peer_id in self.connections
        ):
            return direct
        candidates = self._resolve_locked(PeerSelector.service(target))
        if not candidates:
            return None
        cursor = self._route_cursors.get(target, 0)
        self._route_cursors[target] = cursor + 1
        return candidates[cursor % len(candidates)]

    async def _handle_response(self, connection: _HubConnection, frame: dict[str, Any]) -> None:
        response = _response_from_wire(frame.get("response"))
        async with self._lock:
            delivery = self.deliveries.get(response.task_id)
            if delivery is None:
                return
            if delivery.target_peer_id != connection.peer_id:
                raise WebSocketProtocolError("A peer may only respond to requests delivered to itself")
            del self.deliveries[response.task_id]
            if not delivery.request.expects_response:
                return
            source = self.connections.get(delivery.source_peer_id)
            if source is not None:
                if not self._enqueue_frame_locked(
                    source, {"type": "response", "response": _response_to_wire(response)}
                ):
                    self._close_overloaded_connection(source)


class _WebSocketConnection:
    def __init__(self, settings: WebSocketSettings):
        self.settings = settings
        self.identity: PeerIdentity | None = None
        self.client: httpx.AsyncClient | None = None
        self.websocket: AsyncWebSocketSession | None = None
        self.websocket_context: Any | None = None
        self.reader_task: asyncio.Task[None] | None = None
        self.commands: dict[str, asyncio.Future[Any]] = {}
        self.incoming: asyncio.Queue[RpcRequest] = asyncio.Queue(maxsize=settings.queue_size)
        self.responses: dict[str, RpcResponse] = {}
        self.peer_states: dict[str, PeerRecord] = {}
        self._send_lock = asyncio.Lock()
        self._error: BaseException | None = None
        self._closing = False

    @property
    def connected(self) -> bool:
        return self.websocket is not None and self._error is None

    async def connect(self, identity: PeerIdentity) -> None:
        if self.connected:
            raise RuntimeError("WebSocket JobQueue connection is already active")
        await self.close()
        while True:
            try:
                self.incoming.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.responses.clear()
        self.peer_states.clear()
        self.identity = identity
        self._closing = False
        self._error = None
        self.client = httpx.AsyncClient(timeout=self.settings.command_timeout, trust_env=False)
        try:
            self.websocket_context = aconnect_ws(
                self.settings.url,
                client=self.client,
                max_message_size_bytes=self.settings.max_message_bytes,
                queue_size=self.settings.queue_size,
                keepalive_ping_interval_seconds=self.settings.heartbeat_seconds,
                keepalive_ping_timeout_seconds=self.settings.heartbeat_seconds,
            )
            self.websocket = await self.websocket_context.__aenter__()
            await self._send_frame(
                {
                    "type": "hello",
                    "protocol": PROTOCOL_VERSION,
                    "token": self.settings.token,
                    "identity": _identity_to_wire(identity),
                }
            )
            welcome = _decode_frame(
                await self.websocket.receive_bytes(timeout=self.settings.command_timeout),
                self.settings.max_message_bytes,
            )
            if (
                welcome.get("type") != "welcome"
                or welcome.get("protocol") != PROTOCOL_VERSION
                or welcome.get("peer_id") != identity.peer_id
            ):
                raise WebSocketProtocolError("WebSocket Hub returned an invalid welcome frame")
            self.reader_task = asyncio.create_task(self._reader(), name=f"jobqueue-websocket-read:{identity.peer_id}")
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        self._closing = True
        reader = self.reader_task
        self.reader_task = None
        if reader is not None and reader is not asyncio.current_task():
            reader.cancel()
        websocket = self.websocket
        self.websocket = None
        if reader is not None and reader is not asyncio.current_task():
            await asyncio.gather(reader, return_exceptions=True)
        websocket_context = self.websocket_context
        self.websocket_context = None
        if websocket is not None:
            try:
                await websocket.close()
            except BaseException:
                pass
        if websocket_context is not None:
            try:
                await websocket_context.__aexit__(None, None, None)
            except BaseException:
                pass
        client = self.client
        self.client = None
        if client is not None:
            await client.aclose()
        self._fail_commands(WebSocketBackendError("WebSocket JobQueue connection closed"))
        self._closing = False

    def _fail_commands(self, error: BaseException) -> None:
        for future in self.commands.values():
            if not future.done():
                future.set_exception(error)
        self.commands.clear()

    def ensure_connected(self) -> None:
        if self._error is not None:
            raise WebSocketBackendError(str(self._error)) from self._error
        if not self.connected:
            raise WebSocketBackendError("WebSocket JobQueue connection is not active")

    async def _send_frame(self, frame: dict[str, Any]) -> None:
        payload = _encode_frame(frame, self.settings.max_message_bytes)
        async with self._send_lock:
            websocket = self.websocket
            if websocket is None:
                raise WebSocketBackendError("WebSocket JobQueue connection is not active")
            try:
                await websocket.send_bytes(payload)
            except Exception as exc:
                raise WebSocketBackendError("Failed to send a WebSocket JobQueue frame") from exc

    async def _reader(self) -> None:
        websocket = self.websocket
        if websocket is None:
            return
        try:
            while True:
                frame = _decode_frame(await websocket.receive_bytes(), self.settings.max_message_bytes)
                frame_type = frame.get("type")
                if frame_type == "command_result":
                    command_id = frame.get("id")
                    future = self.commands.pop(command_id, None) if isinstance(command_id, str) else None
                    if future is not None and not future.done():
                        if frame.get("ok") is True:
                            future.set_result(frame.get("result"))
                        else:
                            future.set_exception(WebSocketBackendError(str(frame.get("error", "Hub command failed"))))
                elif frame_type == "request":
                    try:
                        self.incoming.put_nowait(_request_from_wire(frame.get("request")))
                    except asyncio.QueueFull as exc:
                        raise WebSocketBackendError("Incoming WebSocket JobQueue request queue is full") from exc
                elif frame_type == "response":
                    response = _response_from_wire(frame.get("response"))
                    if response.task_id not in self.responses and len(self.responses) >= self.settings.queue_size:
                        raise WebSocketBackendError("Incoming WebSocket JobQueue response queue is full")
                    self.responses[response.task_id] = response
                elif frame_type == "peer_state":
                    record = _record_from_wire(frame.get("peer"))
                    if record.peer_id not in self.peer_states and len(self.peer_states) >= self.settings.queue_size:
                        del self.peer_states[next(iter(self.peer_states))]
                    self.peer_states[record.peer_id] = record
                elif frame_type == "error":
                    raise WebSocketProtocolError(str(frame.get("message", "Hub protocol error")))
                else:
                    raise WebSocketProtocolError("Unsupported frame from WebSocket JobQueue Hub")
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            if not self._closing:
                self._error = exc
                self._fail_commands(WebSocketBackendError(str(exc)))

    async def command(self, operation: str, **data: Any) -> Any:
        self.ensure_connected()
        if len(self.commands) >= self.settings.queue_size:
            raise WebSocketBackendError("Too many concurrent WebSocket JobQueue commands")
        command_id = str(uuid4())
        future = asyncio.get_running_loop().create_future()
        self.commands[command_id] = future
        try:
            await self._send_frame({"type": "command", "id": command_id, "op": operation, **data})
            try:
                async with asyncio.timeout(self.settings.command_timeout):
                    return await future
            except TimeoutError as exc:
                raise WebSocketCommandTimeout(
                    f"WebSocket JobQueue command {operation} exceeded its deadline; outcome is unknown"
                ) from exc
        finally:
            self.commands.pop(command_id, None)
            if not future.done():
                future.cancel()


class WebSocketMessageTransport:
    def __init__(self, connection: _WebSocketConnection):
        self.connection = connection

    async def send(self, request: RpcRequest) -> None:
        result = await self.send_many([request])
        if request.task_id in result.accepted:
            return
        if request.task_id in result.rejected:
            raise WebSocketBackendError(result.rejected[request.task_id])
        raise WebSocketCommandTimeout("WebSocket JobQueue delivery acceptance is unknown")

    async def send_many(self, requests: list[RpcRequest]) -> BatchSendResult:
        if not requests:
            return BatchSendResult()
        try:
            result = await self.connection.command(
                "send_many", requests=[_request_to_wire(request) for request in requests]
            )
        except (WebSocketBackendError, WebSocketCommandTimeout):
            return BatchSendResult(unknown=frozenset(request.task_id for request in requests))
        if not isinstance(result, dict):
            raise WebSocketProtocolError("Hub returned an invalid batch delivery result")
        try:
            return BatchSendResult(
                accepted=frozenset(result.get("accepted", [])),
                rejected=dict(result.get("rejected", {})),
                unknown=frozenset(result.get("unknown", [])),
            )
        except (TypeError, ValueError) as exc:
            raise WebSocketProtocolError("Hub returned an invalid batch delivery result") from exc

    async def receive(self, targets: list[str], peer_id: str | None = None) -> list[RpcRequest]:
        requests = []
        while len(requests) < self.connection.settings.queue_size:
            try:
                requests.append(self.connection.incoming.get_nowait())
            except asyncio.QueueEmpty:
                break
        if not requests:
            self.connection.ensure_connected()
        return requests

    async def consume_responses(self, task_ids: list[str]) -> list[RpcResponse]:
        responses = []
        for task_id in task_ids:
            response = self.connection.responses.pop(task_id, None)
            if response is not None:
                responses.append(response)
        if not responses:
            self.connection.ensure_connected()
        return responses

    async def abandon(self, task_ids: list[str]) -> None:
        if not task_ids:
            return
        try:
            if self.connection.connected:
                await self.connection.command("abandon", task_ids=task_ids)
        finally:
            for task_id in task_ids:
                self.connection.responses.pop(task_id, None)

    async def respond(self, request: RpcRequest, response: RpcResponse) -> None:
        if request.task_id != response.task_id:
            raise ValueError("RPC response task ID does not match its request")
        if not self.connection.connected:
            return
        await self.connection._send_frame({"type": "response", "response": _response_to_wire(response)})


class WebSocketPeerRegistry(PeerRegistryBase):
    LEASE_SECONDS = WebSocketHub.LEASE_SECONDS
    MAINTENANCE_LEASE_SECONDS = WebSocketHub.MAINTENANCE_LEASE_SECONDS
    STOPPED_RETENTION_SECONDS = WebSocketHub.STOPPED_RETENTION_SECONDS

    def __init__(self, connection: _WebSocketConnection):
        self.connection = connection

    async def register(self, identity: PeerIdentity, state: PeerState = "starting") -> PeerRecord:
        result = await self.connection.command("register", identity=_identity_to_wire(identity), state=state)
        return _record_from_wire(result)

    async def renew(self, identity: PeerIdentity) -> bool:
        if not self.connection.connected:
            return False
        return bool(await self.connection.command("renew", identity=_identity_to_wire(identity)))

    async def set_state(self, peer_id: str, state: PeerState, lease_seconds: int | None = None) -> bool:
        if not self.connection.connected:
            return False
        return bool(
            await self.connection.command("set_state", peer_id=peer_id, state=state, lease_seconds=lease_seconds)
        )

    async def unregister(self, peer_id: str) -> bool:
        if not self.connection.connected:
            return False
        return bool(await self.connection.command("unregister", peer_id=peer_id))

    async def lookup(self, peer_id: str) -> PeerRecord | None:
        result = await self.connection.command("lookup", peer_id=peer_id)
        return _record_from_wire(result) if result is not None else None

    async def expire_stale(self) -> list[str]:
        result = await self.connection.command("expire")
        if not isinstance(result, list) or any(not isinstance(peer_id, str) for peer_id in result):
            raise WebSocketProtocolError("Hub returned an invalid expired-peer result")
        return result

    async def resolve(self, selector: PeerSelector | None = None) -> list[PeerRecord]:
        selector = selector or PeerSelector.all()
        result = await self.connection.command("resolve", selector=_selector_to_wire(selector))
        if not isinstance(result, list):
            raise WebSocketProtocolError("Hub returned an invalid peer resolution result")
        return [_record_from_wire(record) for record in result]


class WebSocketJobQueueBackend:
    name = "websocket"

    def __init__(self, settings: WebSocketSettings):
        self.settings = settings
        self.connection = _WebSocketConnection(settings)
        self.transport = WebSocketMessageTransport(self.connection)
        self.registry = WebSocketPeerRegistry(self.connection)

    @classmethod
    def from_config(cls) -> "WebSocketJobQueueBackend":
        return cls(WebSocketSettings.from_config())

    @property
    def ready(self) -> bool:
        return self.connection.connected

    async def start(self, identity: PeerIdentity | None) -> None:
        if identity is None:
            raise ValueError("The WebSocket JobQueue backend requires a configured peer identity")
        await self.connection.connect(identity)

    async def close(self) -> None:
        await self.connection.close()


async def run_websocket_hub(stop_event=None, ready_event=None) -> None:
    """运行配置指定的独立 Hub，供守护进程子进程或命令行入口调用。"""
    settings = WebSocketSettings.from_config()
    hub = WebSocketHub(settings)
    await hub.start()
    if ready_event is not None:
        ready_event.set()
    try:
        while stop_event is None or not stop_event.is_set():
            server_task = hub._server_task
            if server_task is None or server_task.done():
                if server_task is not None:
                    await server_task
                raise RuntimeError("WebSocket JobQueue Hub server stopped unexpectedly")
            await asyncio.sleep(0.2)
    finally:
        await hub.close()


def run_websocket_hub_process(stop_event=None, ready_event=None) -> None:
    asyncio.run(run_websocket_hub(stop_event, ready_event))


if __name__ == "__main__":
    run_websocket_hub_process()
