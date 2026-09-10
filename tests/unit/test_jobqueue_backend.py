"""JobQueue 后端装配和介质无关契约测试。"""

import time
from unittest.mock import patch

from core.config.jobqueue import JobQueueConfig
from core.queue.backend import create_jobqueue_backend
from core.queue.base import JobQueueBase
from core.queue.database import DatabaseJobQueueBackend, DatabaseMessageTransport, DatabasePeerRegistry
from core.queue.errors import RpcProtocolError
from core.queue.transport import BatchSendResult, RpcRequest
from core.queue.websocket import WebSocketJobQueueBackend
from core.tester import func_case, Tester


async def _test_database_backend_is_a_complete_isolated_bundle():
    first = create_jobqueue_backend("database")
    second = create_jobqueue_backend(" DATABASE ")
    assert isinstance(first, DatabaseJobQueueBackend)
    assert isinstance(first.transport, DatabaseMessageTransport)
    assert isinstance(first.registry, DatabasePeerRegistry)
    assert first.registry.transport is first.transport
    assert first is not second and first.registry is not second.registry and first.transport is not second.transport
    assert not first.ready
    await first.start(None)
    assert first.ready
    await first.close()
    return not first.ready


async def _test_backend_factory_obeys_config_without_fallback():
    with patch.object(JobQueueConfig, "jobqueue_backend", "database"):
        configured = create_jobqueue_backend()
    if not isinstance(configured, DatabaseJobQueueBackend):
        return False
    with (
        patch.object(JobQueueConfig, "jobqueue_websocket_mode", "embedded"),
        patch.object(JobQueueConfig, "jobqueue_websocket_url", "ws://127.0.0.1:8765/jobqueue"),
        patch.object(JobQueueConfig, "jobqueue_websocket_queue_size", 1000),
        patch.object(JobQueueConfig, "jobqueue_websocket_max_message_bytes", 1048576),
        patch.object(JobQueueConfig, "jobqueue_websocket_command_timeout", 10),
        patch("core.config.jobqueue.JobQueueSecretConfig.jobqueue_websocket_token", ""),
    ):
        websocket = create_jobqueue_backend("websocket")
    if not isinstance(websocket, WebSocketJobQueueBackend):
        return False
    for name, error_type in (("redis", ValueError), ("", ValueError), (None, ValueError)):
        try:
            if name is None:
                with patch.object(JobQueueConfig, "jobqueue_backend", None):
                    create_jobqueue_backend()
            else:
                create_jobqueue_backend(name)
            return False
        except error_type:
            pass
    return True


async def _test_runtime_injects_registry_and_transport_as_one_bundle():
    class BackendPeer(JobQueueBase):
        pass

    backend = create_jobqueue_backend("database")
    BackendPeer.configure_backend(backend)
    return (
        BackendPeer.backend is backend
        and BackendPeer.registry is backend.registry
        and BackendPeer.transport is backend.transport
    )


async def _test_partial_backend_start_is_closed_transactionally():
    class PartialStartBackend(DatabaseJobQueueBackend):
        closed = False

        async def start(self, identity):
            self._ready = True
            raise RuntimeError("partial backend start")

        async def close(self):
            self.closed = True
            await super().close()

    class FailingPeer(JobQueueBase):
        pass

    backend = PartialStartBackend()
    FailingPeer.configure_backend(backend)
    try:
        await FailingPeer.check_job_queue()
        return False
    except RuntimeError as exc:
        return (
            str(exc) == "partial backend start" and backend.closed and not backend.ready and not FailingPeer.is_running
        )


async def _test_batch_result_must_cover_every_request_once():
    requests = [
        RpcRequest("task-a", "target", "method", None, time.time() + 1),
        RpcRequest("task-b", "target", "method", None, time.time() + 1),
    ]
    try:
        JobQueueBase._validate_batch_result(requests, BatchSendResult(accepted=frozenset({"task-a"})))
        return False
    except RpcProtocolError:
        pass
    try:
        BatchSendResult(accepted=frozenset({"task-a"}), unknown=frozenset({"task-a"}))
        return False
    except ValueError:
        return True


@func_case
async def test_jobqueue_backend(tester: Tester):
    await tester.test(_test_database_backend_is_a_complete_isolated_bundle, "数据库后端完整装配且实例隔离")
    await tester.test(_test_backend_factory_obeys_config_without_fallback, "后端配置严格选择且不静默回退")
    await tester.test(_test_runtime_injects_registry_and_transport_as_one_bundle, "运行时整套注入控制面与数据面")
    await tester.test(_test_partial_backend_start_is_closed_transactionally, "后端部分启动失败后执行关闭回滚")
    await tester.test(_test_batch_result_must_cover_every_request_once, "批量投递结果完整且互斥")
    return tester
