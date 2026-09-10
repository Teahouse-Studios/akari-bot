"""WebSocket JobQueue 完整后端测试。"""

import asyncio
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.config.jobqueue import JobQueueConfig
from core.queue.base import current_peer, JobQueueBase
from core.queue.errors import RpcProtocolError, RpcUnavailableError
from core.queue.peer import PeerSelector, SignalContext
from core.queue.websocket import (
    WebSocketHub,
    WebSocketJobQueueBackend,
    WebSocketSettings,
)
from core.queue.transport import RpcRequest
from core.tester import func_case, Tester


@asynccontextmanager
async def _websocket_peers(
    count: int = 2,
    *,
    token: str = "test-token",
    queue_size: int = 1000,
    max_message_bytes: int = 1048576,
):
    hub_settings = WebSocketSettings(
        url="ws://127.0.0.1:0/jobqueue",
        token=token,
        queue_size=queue_size,
        max_message_bytes=max_message_bytes,
        command_timeout=1,
        heartbeat_seconds=1,
    )
    hub = WebSocketHub(hub_settings)
    await hub.start()
    peers = []
    pollers = []
    try:
        client_settings = WebSocketSettings(
            url=hub.url,
            token=token,
            queue_size=queue_size,
            max_message_bytes=max_message_bytes,
            command_timeout=1,
            heartbeat_seconds=1,
        )
        for index in range(count):

            class WebSocketPeer(JobQueueBase):
                name = f"WEBSOCKET-{index}-{uuid4()}"
                POLL_INTERVAL_SECONDS = 0.001
                backend = WebSocketJobQueueBackend(client_settings)

            WebSocketPeer.configure_peer(
                role="test",
                service="websocket-workers" if index else "websocket-controller",
                node_id=f"websocket-node-{index}",
                capabilities=["rpc", "signals"],
            )
            peers.append(WebSocketPeer)
        pollers = [asyncio.create_task(peer.check_job_queue()) for peer in peers]
        await asyncio.gather(*(peer.wait_ready(timeout=2) for peer in peers))
        # wait_ready 只保证各 Peer 已注册；ready/welcome 握手仍可能在其它 Peer 的
        # 处理任务或 Hub 出站队列中。测试开始前等待控制面静默，避免 queue_size=1
        # 的背压用例与启动握手竞争同一个命令槽位。
        async with asyncio.timeout(2):
            while True:
                async with hub._lock:
                    deliveries_pending = bool(hub.deliveries)
                commands_pending = any(peer.backend.connection.commands for peer in peers)
                handlers_pending = any(peer._process_tasks for peer in peers)
                if not deliveries_pending and not commands_pending and not handlers_pending:
                    break
                await asyncio.sleep(0.001)
        yield hub, peers
    finally:
        for peer in peers:
            if peer.backend.ready:
                await peer.begin_shutdown()
        await asyncio.gather(*(peer.cancel_process_tasks() for peer in peers), return_exceptions=True)
        for poller in pollers:
            poller.cancel()
        await asyncio.gather(*pollers, return_exceptions=True)
        await hub.close()


async def _test_websocket_roundtrip_nested_callback_and_bound_identity():
    async with _websocket_peers() as (_, peers):
        caller, receiver = peers

        @caller.register("websocket.callback")
        async def callback(payload):
            return payload + 1

        @receiver.register("websocket.outer")
        async def outer(payload):
            assert current_peer.get() is receiver
            return await receiver.call(caller.name, "websocket.callback", payload, timeout=1)

        @receiver.on_signal("websocket.source")
        async def source(context: SignalContext, payload):
            return context.source_peer_id

        result = await caller.call(receiver.name, "websocket.outer", 8, timeout=1)
        report = await caller.gather_signal("websocket.source", None, PeerSelector.peer(receiver.name), timeout=1)
        return result == 9 and report.results[receiver.name][0] == caller.name


async def _test_websocket_signal_fanout_and_service_anycast():
    async with _websocket_peers(3) as (_, peers):
        controller, worker_a, worker_b = peers
        received = {worker_a.name: 0, worker_b.name: 0}

        for worker in (worker_a, worker_b):

            @worker.register("websocket.worker")
            async def worker_rpc(payload, *, bound_worker=worker):
                return bound_worker.name

            @worker.on_signal("websocket.invalidate")
            async def handler(context, payload, *, bound_worker=worker):
                received[bound_worker.name] += 1
                return context.target_peer_id

        report = await controller.gather_signal(
            "websocket.invalidate",
            {"version": 1},
            PeerSelector.service("websocket-workers"),
            timeout=1,
        )
        routed = {await controller.call("websocket-workers", "websocket.worker", None, timeout=1) for _ in range(4)}
        return (
            received == {worker_a.name: 1, worker_b.name: 1}
            and not report.errors
            and set(report.results) == {worker_a.name, worker_b.name}
            and routed == {worker_a.name, worker_b.name}
        )


async def _test_websocket_disconnect_wakes_outstanding_call():
    async with _websocket_peers() as (_, peers):
        caller, receiver = peers
        started = asyncio.Event()

        @receiver.register("websocket.hang")
        async def hang(payload):
            started.set()
            await asyncio.Event().wait()

        call = asyncio.create_task(caller.call(receiver.name, "websocket.hang", None, timeout=2))
        await asyncio.wait_for(started.wait(), 1)
        await receiver.backend.close()
        try:
            await asyncio.wait_for(call, 1)
            return False
        except RpcUnavailableError:
            return not caller._pending


def _test_websocket_settings_use_mode_and_url_as_single_source():
    with (
        patch.object(JobQueueConfig, "jobqueue_websocket_mode", " EMBEDDED "),
        patch.object(JobQueueConfig, "jobqueue_websocket_url", " ws://localhost:8766 "),
        patch("core.config.jobqueue.JobQueueSecretConfig.jobqueue_websocket_token", ""),
    ):
        settings = WebSocketSettings.from_config()
    if (
        settings.mode != "embedded"
        or not settings.embedded
        or settings.url != "ws://localhost:8766/jobqueue"
        or settings.bind_host != "localhost"
        or settings.bind_port != 8766
        or settings.path != "/jobqueue"
    ):
        return False

    external = WebSocketSettings(mode="external", url="wss://queue.example.com/ws", token="secret")
    if external.embedded or external.bind_host != "queue.example.com" or external.bind_port != 443:
        return False

    invalid_settings = (
        {"mode": "automatic"},
        {"url": "ws://127.0.0.1:not-a-port/jobqueue"},
        {"url": "ws://user:password@127.0.0.1:8765/jobqueue"},
        {"url": "ws://127.0.0.1:8765/jobqueue#fragment"},
        {"mode": "embedded", "url": "wss://127.0.0.1:8765/jobqueue"},
        {"mode": "embedded", "url": "ws://0.0.0.0:8765/jobqueue", "token": "secret"},
        {"mode": "external", "url": "ws://queue.example.com/jobqueue", "token": "secret"},
    )
    for kwargs in invalid_settings:
        try:
            WebSocketSettings(**kwargs)
            return False
        except (TypeError, ValueError):
            pass

    with (
        patch.object(JobQueueConfig, "jobqueue_websocket_mode", "embedded"),
        patch.object(JobQueueConfig, "jobqueue_websocket_url", "ws://127.0.0.1:0/jobqueue"),
        patch("core.config.jobqueue.JobQueueSecretConfig.jobqueue_websocket_token", ""),
    ):
        try:
            WebSocketSettings.from_config()
            return False
        except ValueError:
            return True


async def _test_websocket_authentication_and_remote_token_requirement():
    try:
        WebSocketSettings(mode="external", url="ws://example.com/jobqueue", token="")
        return False
    except ValueError:
        pass
    hub = WebSocketHub(WebSocketSettings(url="ws://127.0.0.1:0/jobqueue", token="correct", command_timeout=0.5))
    await hub.start()
    backend = WebSocketJobQueueBackend(WebSocketSettings(url=hub.url, token="incorrect", command_timeout=0.5))
    identity = None

    class AuthenticationPeer(JobQueueBase):
        name = f"AUTH-{uuid4()}"

    AuthenticationPeer.configure_backend(backend)
    identity = AuthenticationPeer.configure_peer(role="test", service="auth", node_id="auth-node")
    try:
        await backend.start(identity)
        return False
    except Exception:
        return not backend.ready
    finally:
        await backend.close()
        await hub.close()


async def _test_websocket_limits_duplicate_identity_and_backpressure():
    async with _websocket_peers(queue_size=1) as (hub, peers):
        caller, receiver = peers
        duplicate = WebSocketJobQueueBackend(receiver.backend.settings)
        try:
            await duplicate.start(receiver.identity)
            return False
        except Exception:
            if duplicate.ready:
                return False
        finally:
            await duplicate.close()

        target_connection = hub.connections[receiver.name]
        while not target_connection.outbound.empty():
            await asyncio.sleep(0.001)
        target_connection.sender_task.cancel()
        await asyncio.gather(target_connection.sender_task, return_exceptions=True)

        accepted = await caller.emit_signal("websocket.backpressure", None, PeerSelector.peer(receiver.name), timeout=1)
        rejected = await caller.emit_signal("websocket.backpressure", None, PeerSelector.peer(receiver.name), timeout=1)
        result = (
            receiver.name in accepted.deliveries
            and receiver.name in rejected.errors
            and "backpressure" in rejected.errors[receiver.name].lower()
        )
        target_connection.sender_task = asyncio.create_task(hub._sender(target_connection))
        await asyncio.sleep(0.01)
        return result


async def _test_websocket_frame_size_limit_cleans_waiter():
    async with _websocket_peers(max_message_bytes=2048) as (hub, peers):
        caller, receiver = peers

        @receiver.register("websocket.large")
        async def large(payload):
            return payload

        try:
            await caller.call(receiver.name, "websocket.large", "x" * 4096, timeout=1)
            return False
        except RpcProtocolError as exc:
            # Peer ready/welcome 信号可能仍在同一 Hub 中异步收尾；这里只验证超限调用
            # 自身没有遗留等待方或投递，避免把无关生命周期投递误判为泄漏。
            return not caller._pending and exc.task_id not in hub.deliveries


async def _test_websocket_expired_delivery_is_released():
    async with _websocket_peers() as (hub, peers):
        caller, receiver = peers
        receiver.pause_event.clear()
        request = RpcRequest(
            task_id=str(uuid4()),
            target=receiver.name,
            method="websocket.never-consumed",
            payload=None,
            deadline=time.time() + 0.01,
            source_peer_id=caller.name,
        )
        await caller.transport.send(request)
        await asyncio.sleep(0.02)
        async with hub._lock:
            hub._expire_locked()
        async with asyncio.timeout(1):
            while not (responses := await caller.transport.consume_responses([request.task_id])):
                await asyncio.sleep(0.001)
        receiver.pause_event.set()
        return responses[0].status == "timeout" and request.task_id not in hub.deliveries


async def _test_websocket_hub_restart_and_idempotent_close():
    settings = WebSocketSettings(
        url="ws://127.0.0.1:0/jobqueue",
        token="restart-test-token",
        command_timeout=1,
    )
    hub = WebSocketHub(settings)
    await hub.start()
    first_port = hub.bound_port
    await hub.close()
    await hub.close()
    await hub.start()
    try:
        return first_port > 0 and hub.bound_port > 0 and hub._server_task is not None and not hub._server_task.done()
    finally:
        await hub.close()


async def _test_websocket_independent_process_roundtrip():
    token = "process-test-token"
    hub = WebSocketHub(
        WebSocketSettings(
            url="ws://127.0.0.1:0/jobqueue",
            token=token,
            command_timeout=2,
            heartbeat_seconds=2,
        )
    )
    await hub.start()
    worker = Path(__file__).resolve().parents[1] / "helpers" / "websocket_rpc_worker.py"
    environment = {**os.environ, "CI": "1", "PYTHONIOENCODING": "UTF-8"}
    processes = []
    try:
        server = await asyncio.create_subprocess_exec(
            sys.executable,
            str(worker),
            hub.url,
            "WS-RPC-B",
            token,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
        )
        processes.append(server)
        async with asyncio.timeout(15):
            while True:
                line = await server.stdout.readline()
                if not line:
                    raise AssertionError((await server.stderr.read()).decode("utf-8", errors="replace"))
                if line.strip() == b"WS_RPC_READY":
                    break
        caller = await asyncio.create_subprocess_exec(
            sys.executable,
            str(worker),
            hub.url,
            "WS-RPC-A",
            token,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
        )
        processes.append(caller)
        caller_output, server_output = await asyncio.wait_for(
            asyncio.gather(caller.communicate(), server.communicate()), timeout=35
        )
        for process, output in ((caller, caller_output), (server, server_output)):
            if process.returncode != 0:
                raise AssertionError(b"\n".join(output).decode("utf-8", errors="replace"))
        return (
            b'"websocket_rpc_process": "passed"' in caller_output[0]
            and b'"signals": "passed"' in caller_output[0]
            and b'"callbacks": 7' in caller_output[0]
        )
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
        await asyncio.gather(*(process.wait() for process in processes), return_exceptions=True)
        await hub.close()


@func_case
async def test_jobqueue_websocket_backend(tester: Tester):
    await tester.test(
        _test_websocket_roundtrip_nested_callback_and_bound_identity,
        "WebSocket 双向 RPC、反向调用与连接身份绑定",
    )
    await tester.test(
        _test_websocket_signal_fanout_and_service_anycast,
        "WebSocket 逐实例信号与同服务任播",
    )
    await tester.test(
        _test_websocket_disconnect_wakes_outstanding_call,
        "WebSocket 目标断线立即唤醒调用方",
    )
    await tester.test(
        _test_websocket_settings_use_mode_and_url_as_single_source,
        "WebSocket 部署模式与统一 URL 配置解析",
    )
    await tester.test(
        _test_websocket_authentication_and_remote_token_requirement,
        "WebSocket 鉴权及远程连接安全约束",
    )
    await tester.test(
        _test_websocket_limits_duplicate_identity_and_backpressure,
        "WebSocket 重复身份拒绝与有界队列背压",
    )
    await tester.test(
        _test_websocket_frame_size_limit_cleans_waiter,
        "WebSocket 帧大小限制与等待方清理",
    )
    await tester.test(
        _test_websocket_expired_delivery_is_released,
        "WebSocket 过期投递关联释放与超时回包",
    )
    await tester.test(
        _test_websocket_hub_restart_and_idempotent_close,
        "WebSocket Hub 重启与重复关闭安全性",
    )
    await tester.test(
        _test_websocket_independent_process_roundtrip,
        "WebSocket 独立进程发现、信号、RPC 与反向调用",
    )
    return tester
