"""在不访问 JobQueue ORM 表的情况下验证共享运行时契约。"""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from core.queue.base import current_peer, JobQueueBase
from core.queue.errors import RpcUnavailableError
from core.queue.memory import InMemoryBroker, InMemoryJobQueueBackend
from core.queue.peer import PeerSelector
from core.tester import func_case, Tester


@asynccontextmanager
async def _memory_peers(count: int = 2):
    broker = InMemoryBroker()
    peers = []
    pollers = []
    for index in range(count):

        class MemoryPeer(JobQueueBase):
            name = f"MEMORY-{index}-{uuid4()}"
            POLL_INTERVAL_SECONDS = 0.001
            backend = InMemoryJobQueueBackend(broker)

        MemoryPeer.configure_peer(
            role="test",
            service="memory-workers" if index else "memory-controller",
            node_id=f"memory-node-{index}",
            capabilities=["rpc", "signals"],
        )
        peers.append(MemoryPeer)
    try:
        pollers = [asyncio.create_task(peer.check_job_queue()) for peer in peers]
        await asyncio.gather(*(peer.wait_ready(timeout=1) for peer in peers))
        yield peers
    finally:
        await asyncio.gather(*(peer.begin_shutdown() for peer in peers))
        await asyncio.gather(*(peer.cancel_process_tasks() for peer in peers))
        for poller in pollers:
            poller.cancel()
        await asyncio.gather(*pollers, return_exceptions=True)


async def _test_memory_backend_roundtrip_and_nested_callback():
    async with _memory_peers() as (caller, receiver):

        @caller.register("memory.callback")
        async def callback(payload):
            return payload + 1

        @receiver.register("memory.outer")
        async def outer(payload):
            assert current_peer.get() is receiver
            return await receiver.call(caller.name, "memory.callback", payload, timeout=1)

        result = await caller.call(receiver.name, "memory.outer", 8, timeout=1)
        return result == 9 and not caller._pending and not receiver._pending


async def _test_memory_backend_signal_fanout_and_ack():
    async with _memory_peers(3) as peers:
        controller, worker_a, worker_b = peers
        received = {worker_a.name: 0, worker_b.name: 0}

        for worker in (worker_a, worker_b):

            async def handler(context, payload, *, bound_worker=worker):
                received[bound_worker.name] += 1
                return {"peer": context.target_peer_id, "value": payload["value"]}

            worker.on_signal("memory.invalidate", handler)

        report = await controller.gather_signal(
            "memory.invalidate",
            {"value": 4},
            PeerSelector.service("memory-workers"),
            timeout=1,
        )
        return (
            received == {worker_a.name: 1, worker_b.name: 1}
            and not report.errors
            and set(report.results) == {worker_a.name, worker_b.name}
            and all(result[0]["value"] == 4 for result in report.results.values())
        )


async def _test_memory_backend_peer_loss_wakes_outstanding_call():
    async with _memory_peers() as (caller, receiver):
        started = asyncio.Event()

        @receiver.register("memory.hang")
        async def hang(payload):
            started.set()
            await asyncio.Event().wait()

        call = asyncio.create_task(caller.call(receiver.name, "memory.hang", None, timeout=2))
        await asyncio.wait_for(started.wait(), 1)
        await receiver.registry.unregister(receiver.name)
        try:
            await asyncio.wait_for(call, 1)
            return False
        except RpcUnavailableError:
            return not caller._pending


@func_case
async def test_jobqueue_memory_backend(tester: Tester):
    await tester.test(_test_memory_backend_roundtrip_and_nested_callback, "内存后端双向 RPC 与反向调用")
    await tester.test(_test_memory_backend_signal_fanout_and_ack, "内存后端逐实例信号与独立 ACK")
    await tester.test(_test_memory_backend_peer_loss_wakes_outstanding_call, "内存后端实例失效唤醒调用方")
    return tester
