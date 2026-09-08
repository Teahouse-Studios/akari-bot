"""Peer discovery, anycast and fan-out signal tests over real queue rows."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from core.alive import Alive
from core.builtins.session.info import FetchedSessionInfo
from core.constants import Info
from core.database.models import JobQueuePeersTable, JobQueuesTable
from core.queue.base import JobQueueBase
from core.queue.errors import RpcProtocolError, RpcTimeoutError, RpcUnavailableError
from core.queue.peer import PeerDirectory, PeerSelector, ServiceRoute
from core.queue.rpc import remote, signal
from core.queue.server import JobQueueServer
from core.queue.transport import RpcRequest
from core.tester import Tester, func_case


@asynccontextmanager
async def _peer_cluster():
    previous_peer = (Info.peer_id, Info.peer_role)
    previous_alive = Alive.values.copy()

    class Controller(JobQueueBase):
        name = f"PEER-CONTROLLER-{uuid4()}"
        POLL_INTERVAL_SECONDS = 0.005
        RECONCILE_INTERVAL_SECONDS = 0.02

    class WorkerA(JobQueueBase):
        name = f"PEER-WORKER-A-{uuid4()}"
        POLL_INTERVAL_SECONDS = 0.005
        RECONCILE_INTERVAL_SECONDS = 0.02

    class WorkerB(JobQueueBase):
        name = f"PEER-WORKER-B-{uuid4()}"
        POLL_INTERVAL_SECONDS = 0.005
        RECONCILE_INTERVAL_SECONDS = 0.02

    Controller.configure_peer(role="server", service="controller", capabilities=["signals"])
    WorkerA.configure_peer(
        role="client",
        service="workers",
        capabilities=["signals", "jobs"],
        metadata={"ctx_slot_index": 11},
    )
    WorkerB.configure_peer(
        role="client",
        service="workers",
        capabilities=["signals", "jobs"],
        metadata={"ctx_slot_index": 22},
    )
    peers = (Controller, WorkerA, WorkerB)
    pollers = [asyncio.create_task(peer.check_job_queue()) for peer in peers]
    try:
        async with asyncio.timeout(2):
            while len(await PeerDirectory.resolve(PeerSelector.peer(*(peer.name for peer in peers)))) != len(peers):
                await asyncio.sleep(0.005)
        yield peers
    finally:
        await asyncio.gather(*(peer.begin_shutdown() for peer in peers))
        await asyncio.gather(*(peer.cancel_process_tasks() for peer in peers))
        for poller in pollers:
            poller.cancel()
        await asyncio.gather(*pollers, return_exceptions=True)
        peer_ids = [peer.name for peer in peers]
        await JobQueuesTable.filter(source_peer_id__in=peer_ids).delete()
        await JobQueuesTable.filter(target_peer__in=peer_ids).delete()
        await JobQueuePeersTable.filter(peer_id__in=peer_ids).delete()
        Info.peer_id, Info.peer_role = previous_peer
        Alive.values.clear()
        Alive.values.update(previous_alive)


async def _test_instances_discover_each_other_and_fan_out_once():
    seen = {}
    async with _peer_cluster() as (controller, worker_a, worker_b):
        for worker in (worker_a, worker_b):

            @worker.on_signal("audit.broadcast")
            async def receive(context, payload, worker=worker):
                seen[worker.name] = (context.event_id, context.source_peer_id, payload)
                return worker.name

        receipt = await controller.emit_signal(
            "audit.broadcast",
            {"version": 7},
            PeerSelector(roles=("client",), services=("workers",), capabilities=("jobs",)),
            timeout=2,
        )
        async with asyncio.timeout(2):
            while True:
                rows = await JobQueuesTable.filter(correlation_id=receipt.event_id)
                if len(seen) == 2 and len(rows) == 2 and all(row.status == "done" for row in rows):
                    break
                await asyncio.sleep(0.005)
        Alive.values.pop(worker_a.name, None)
        await JobQueueServer.ensure_target_available(worker_a.name)
        return (
            set(receipt.deliveries) == {worker_a.name, worker_b.name}
            and all(event_id == receipt.event_id for event_id, _, _ in seen.values())
            and all(source == controller.name for _, source, _ in seen.values())
            and all(payload == {"version": 7} for _, _, payload in seen.values())
            and {row.claimed_by for row in rows} == {worker_a.name, worker_b.name}
            and all(row.status == "done" for row in rows)
            and set(Alive.peer_ids(service="workers")) == {worker_a.name, worker_b.name}
            and Alive.is_alive(worker_a.name)
        )


async def _test_startup_ready_and_welcome_are_mutual():
    previous_peer = (Info.peer_id, Info.peer_role)
    previous_alive = Alive.values.copy()
    ready_seen = asyncio.Event()
    welcome_seen = asyncio.Event()

    class Observer(JobQueueBase):
        name = f"PEER-OBSERVER-{uuid4()}"
        POLL_INTERVAL_SECONDS = 0.005

    class Newcomer(JobQueueBase):
        name = f"PEER-NEWCOMER-{uuid4()}"
        POLL_INTERVAL_SECONDS = 0.005

    Observer.configure_peer(role="server", service="observers")
    Newcomer.configure_peer(role="client", service="newcomers")

    @Observer.on_signal("peer.ready")
    async def observe_ready(_context, payload):
        if payload.get("peer_id") == Newcomer.name:
            ready_seen.set()

    @Newcomer.on_signal("peer.welcome")
    async def observe_welcome(_context, payload):
        if payload.get("peer_id") == Observer.name:
            welcome_seen.set()

    pollers = []
    try:
        pollers.append(asyncio.create_task(Observer.check_job_queue()))
        await Observer.wait_ready(timeout=2)
        pollers.append(asyncio.create_task(Newcomer.check_job_queue()))
        await Newcomer.wait_ready(timeout=2)
        async with asyncio.timeout(2):
            await asyncio.gather(ready_seen.wait(), welcome_seen.wait())
        return Alive.is_alive(Observer.name) and Alive.is_alive(Newcomer.name)
    finally:
        await asyncio.gather(Observer.begin_shutdown(), Newcomer.begin_shutdown())
        await asyncio.gather(Observer.cancel_process_tasks(), Newcomer.cancel_process_tasks())
        for poller in pollers:
            poller.cancel()
        await asyncio.gather(*pollers, return_exceptions=True)
        peer_ids = [Observer.name, Newcomer.name]
        await JobQueuesTable.filter(source_peer_id__in=peer_ids).delete()
        await JobQueuesTable.filter(target_peer__in=peer_ids).delete()
        await JobQueuePeersTable.filter(peer_id__in=peer_ids).delete()
        Info.peer_id, Info.peer_role = previous_peer
        Alive.values.clear()
        Alive.values.update(previous_alive)


async def _test_auto_identity_is_unique_per_process_lifecycle():
    previous_peer = (Info.peer_id, Info.peer_role)

    class AutoPeer(JobQueueBase):
        pass

    class NamedPeer(JobQueueBase):
        name = "PEER-NAMED"

    try:
        first = AutoPeer.configure_peer(role="worker", service="jobs")
        second = AutoPeer.configure_peer(role="worker", service="jobs")
        named = NamedPeer.configure_peer(role="worker", service="jobs")
        return (
            first.peer_id != second.peer_id
            and named.peer_id == "PEER-NAMED"
            and second.metadata["pid"] == os.getpid()
            and bool(second.node_id)
        )
    finally:
        Info.peer_id, Info.peer_role = previous_peer


def _test_peer_selector_normalizes_and_validates_targets():
    selector = PeerSelector(
        peer_ids=["peer-a", "peer-a"],
        roles=["client"],
        services=["workers"],
    )
    if selector.peer_ids != ("peer-a",) or selector.roles != ("client",):
        return False
    try:
        PeerSelector(roles="client")
    except TypeError:
        pass
    else:
        return False
    try:
        PeerSelector(peer_ids=("",))
    except ValueError:
        return True
    return False


async def _test_stopped_peer_cannot_be_revived_by_late_ready_signal():
    previous_alive = Alive.values.copy()
    peer_id = f"PEER-ORDER-{uuid4()}"

    class Observer(JobQueueBase):
        name = f"PEER-OBSERVER-{uuid4()}"

    stopped = {
        "peer_id": peer_id,
        "role": "client",
        "service": "ordered",
        "state": "stopped",
        "capabilities": [],
        "metadata": {},
    }
    ready = {**stopped, "state": "ready"}
    try:
        await JobQueuePeersTable.create(
            peer_id=peer_id,
            role="client",
            service="ordered",
            state="stopped",
            capabilities=[],
            metadata={},
            lease_until=datetime.now(UTC),
        )
        await Observer._dispatch_signal(
            RpcRequest(
                "stop",
                Observer.name,
                "peer.stopped",
                stopped,
                float("inf"),
                source_peer_id=peer_id,
                message_kind="signal",
            )
        )
        await Observer._dispatch_signal(
            RpcRequest(
                "ready",
                Observer.name,
                "peer.ready",
                ready,
                float("inf"),
                source_peer_id=peer_id,
                message_kind="signal",
            )
        )
        return not Alive.is_alive(peer_id) and Alive.values[peer_id]["state"] == "stopped"
    finally:
        await JobQueuePeersTable.filter(peer_id=peer_id).delete()
        Alive.values.clear()
        Alive.values.update(previous_alive)


async def _test_ready_peer_ignores_late_stopped_signal():
    previous_alive = Alive.values.copy()
    peer_id = f"PEER-LATE-STOP-{uuid4()}"

    class Observer(JobQueueBase):
        name = f"PEER-OBSERVER-{uuid4()}"

    stopped_seen = False

    @Observer.on_signal("peer.stopped")
    async def observe_stopped(_context, _payload):
        nonlocal stopped_seen
        stopped_seen = True

    try:
        await JobQueuePeersTable.create(
            peer_id=peer_id,
            role="client",
            service="ordered",
            state="ready",
            capabilities=[],
            metadata={},
            lease_until=datetime.now(UTC) + timedelta(seconds=30),
        )
        Observer._update_peer_cache((await PeerDirectory.lookup(peer_id)).snapshot())
        await Observer._dispatch_signal(
            RpcRequest(
                "late-stop",
                Observer.name,
                "peer.stopped",
                {
                    "peer_id": peer_id,
                    "role": "client",
                    "service": "ordered",
                    "state": "stopped",
                    "capabilities": [],
                    "metadata": {},
                },
                float("inf"),
                source_peer_id=peer_id,
                message_kind="signal",
            )
        )
        return Alive.is_alive(peer_id) and not stopped_seen
    finally:
        await JobQueuePeersTable.filter(peer_id=peer_id).delete()
        Alive.values.clear()
        Alive.values.update(previous_alive)


async def _test_lifecycle_signal_rejects_non_object_payload():
    class Observer(JobQueueBase):
        name = f"PEER-OBSERVER-{uuid4()}"

    try:
        await Observer._dispatch_signal(
            RpcRequest(
                "invalid-lifecycle",
                Observer.name,
                "peer.ready",
                "not-an-object",
                float("inf"),
                source_peer_id="PEER-INVALID",
                message_kind="signal",
            )
        )
    except RpcProtocolError:
        return True
    return False


async def _test_typed_signal_gathers_independent_acknowledgements():
    @signal("audit.typed", timeout=2)
    async def typed_signal(version: int) -> str: ...

    async with _peer_cluster() as (controller, worker_a, worker_b):
        for label, worker in (("A", worker_a), ("B", worker_b)):

            def make_handler(_label):
                async def handle(version: int) -> str:
                    return f"{_label}:{version}"

                return handle

            typed_signal.bind(worker)(make_handler(label))

        report = await typed_signal.using(controller).gather(PeerSelector.service("workers"), 9)
        values = {peer_id: result[0] for peer_id, result in report.results.items()}
        return (
            set(values) == {worker_a.name, worker_b.name}
            and set(values.values()) == {"A:9", "B:9"}
            and not report.errors
        )


async def _test_signal_failure_is_isolated_per_target():
    @signal("audit.partial-failure", timeout=2)
    async def partial_failure(version: int) -> str: ...

    async with _peer_cluster() as (controller, worker_a, worker_b):

        @partial_failure.bind(worker_a)
        async def succeed(version: int) -> str:
            return f"ok:{version}"

        @partial_failure.bind(worker_b)
        async def fail(version: int) -> str:
            del version
            raise RuntimeError("expected target failure")

        report = await partial_failure.using(controller).gather(PeerSelector.service("workers"), 10)
        return (
            report.results == {worker_a.name: ["ok:10"]}
            and set(report.errors) == {worker_b.name}
            and "expected target failure" in report.errors[worker_b.name]
        )


async def _test_service_target_remains_anycast_for_load_balancing():
    calls = []

    @remote("audit.anycast", target="workers", timeout=2)
    async def anycast(value: int) -> str: ...

    async with _peer_cluster() as (controller, worker_a, worker_b):
        for worker in (worker_a, worker_b):

            def make_handler(_worker):
                async def handle(value: int) -> str:
                    calls.append(_worker.name)
                    return f"{_worker.name}:{value}"

                return handle

            anycast.bind(worker)(make_handler(worker))

        result = await anycast.using(controller)(4)
        row = await JobQueuesTable.filter(action=anycast.name).order_by("-timestamp").first()
        return len(calls) == 1 and result == f"{calls[0]}:4" and row.claimed_by == calls[0]


async def _test_service_route_is_stable_and_distributes_routing_keys():
    async with _peer_cluster() as (controller, worker_a, worker_b):
        routes = [ServiceRoute("workers", f"scene-{index}", role="client") for index in range(64)]
        first = [await controller.resolve_target(route) for route in routes]
        second = [await controller.resolve_target(route) for route in routes]
        return first == second and set(first) == {worker_a.name, worker_b.name}


async def _test_draining_instance_is_removed_from_new_delivery_snapshots():
    async with _peer_cluster() as (controller, worker_a, worker_b):
        await worker_a.begin_shutdown()
        routed_peer = await controller.resolve_target(ServiceRoute("workers", "scene-1", role="client"))
        receipt = await controller.emit_signal("audit.after-drain", None, PeerSelector.service("workers"), timeout=2)
        async with asyncio.timeout(2):
            while worker_a.name in Alive.peer_ids(service="workers"):
                await asyncio.sleep(0.005)
        return routed_peer == worker_b.name and set(receipt.deliveries) == {worker_b.name}


async def _test_maintenance_temporarily_removes_instance_from_stable_routes():
    routing_key = f"maintenance-{uuid4()}"
    maintenance_seen = asyncio.Event()
    resumed_seen = asyncio.Event()
    async with _peer_cluster() as (controller, worker_a, worker_b):
        route = ServiceRoute("workers", routing_key, role="client")
        original_peer_id = await controller.resolve_target(route)
        original_peer = worker_a if original_peer_id == worker_a.name else worker_b
        other_peer = worker_b if original_peer is worker_a else worker_a

        @controller.on_signal("peer.maintenance")
        async def observe_maintenance(_context, payload):
            if payload.get("peer_id") == original_peer.name:
                maintenance_seen.set()

        @controller.on_signal("peer.resumed")
        async def observe_resumed(_context, payload):
            if payload.get("peer_id") == original_peer.name:
                resumed_seen.set()

        async with original_peer.maintenance_window():
            during_maintenance = await controller.resolve_target(route)
            registry_state = (await JobQueuePeersTable.get(peer_id=original_peer.name)).state
            async with asyncio.timeout(2):
                await maintenance_seen.wait()
        after_maintenance = await controller.resolve_target(route)
        async with asyncio.timeout(2):
            await resumed_seen.wait()
            while not Alive.is_alive(original_peer.name):
                await asyncio.sleep(0.005)
        return (
            during_maintenance == other_peer.name
            and registry_state == "maintenance"
            and after_maintenance == original_peer.name
        )


async def _test_fetched_session_metadata_matches_authoritative_route():
    target_id = f"workers|Group|{uuid4()}"
    async with _peer_cluster() as (controller, worker_a, worker_b):
        selected = await controller.resolve_target(ServiceRoute("workers", target_id, role="client"))
        session = await FetchedSessionInfo.assign(
            target_id=target_id,
            target_from="workers|Group",
            client_name="workers",
            fetch=True,
        )
        expected_slot = 11 if selected == worker_a.name else 22
        return selected in {worker_a.name, worker_b.name} and session.ctx_slot == expected_slot


async def _test_authoritative_registry_rejects_stale_alive_entry():
    previous_alive = Alive.values.copy()
    peer_id = f"PEER-STALE-{uuid4()}"
    try:
        Alive.refresh_peer(
            peer_id,
            "stale",
            role="client",
            state="ready",
            lease_until=datetime.now(UTC) + timedelta(seconds=30),
        )
        try:
            await JobQueueServer.ensure_target_available(peer_id)
        except RpcUnavailableError:
            return Alive.is_alive(peer_id)
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(previous_alive)


async def _test_unleased_cache_is_not_routable():
    previous_alive = Alive.values.copy()
    service = f"PEER-LEGACY-{uuid4()}"
    try:
        Alive.refresh_peer(
            f"TEST-PEER-{service}",
            service,
            metadata={
                "target_prefix_list": [f"{service}|Group"],
                "sender_prefix_list": [service],
            },
        )
        try:
            await JobQueueServer.ensure_target_available(service)
        except RpcUnavailableError:
            return not Alive.is_alive(service)
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(previous_alive)


async def _test_route_resolution_obeys_rpc_deadline():
    async def slow_lookup(*_args, **_kwargs):
        await asyncio.sleep(1)

    rpc_timed_out = False
    with patch.object(PeerDirectory, "select_route", new=slow_lookup):
        try:
            await JobQueueBase.submit(
                ServiceRoute("workers", "scene-timeout", role="client"),
                "audit.never",
                None,
                timeout=0.01,
            )
        except RpcTimeoutError as exc:
            rpc_timed_out = exc.target == "workers"
    signal_timed_out = False
    with patch.object(PeerDirectory, "resolve", new=slow_lookup):
        try:
            await JobQueueBase.emit_signal("audit.never", None, PeerSelector.all(), timeout=0.01)
        except RpcTimeoutError as exc:
            signal_timed_out = exc.target == "fan-out"
    return rpc_timed_out and signal_timed_out


async def _test_expired_instance_is_removed_and_direct_waiter_is_released():
    previous_alive = Alive.values.copy()
    peer_id = f"PEER-EXPIRED-{uuid4()}"
    task_id = None
    try:
        await JobQueuePeersTable.create(
            peer_id=peer_id,
            role="client",
            service="expired",
            state="ready",
            capabilities=[],
            metadata={},
            lease_until=datetime.now(UTC) - timedelta(seconds=1),
        )
        task_id = await JobQueueBase.submit(peer_id, "audit.never", None, timeout=2)
        await PeerDirectory.refresh_alive_cache()
        JobQueueBase._update_peer_cache(
            {
                "peer_id": peer_id,
                "role": "client",
                "service": "expired",
                "state": "ready",
                "capabilities": [],
                "metadata": {},
            }
        )
        peer = await JobQueuePeersTable.get(peer_id=peer_id)
        row = await JobQueuesTable.get(task_id=task_id)
        return (
            peer.state == "stopped"
            and row.status == "failed"
            and row.result["error"]["code"] == "unavailable"
            and not Alive.is_alive(peer_id)
        )
    finally:
        await JobQueuePeersTable.filter(peer_id=peer_id).delete()
        if task_id is not None:
            await JobQueuesTable.filter(task_id=task_id).delete()
        Alive.values.clear()
        Alive.values.update(previous_alive)


@func_case
async def test_peer_signals(tester: Tester):
    await tester.test(_test_auto_identity_is_unique_per_process_lifecycle, "进程生命周期身份唯一且可辨认")
    await tester.test(_test_peer_selector_normalizes_and_validates_targets, "广播选择器规范化并拒绝歧义目标")
    await tester.test(_test_stopped_peer_cannot_be_revived_by_late_ready_signal, "生命周期信号乱序不复活实例")
    await tester.test(_test_ready_peer_ignores_late_stopped_signal, "迟到停止信号不能错误摘除 ready 实例")
    await tester.test(_test_lifecycle_signal_rejects_non_object_payload, "生命周期信号拒绝非对象载荷")
    await tester.test(
        _test_instances_discover_each_other_and_fan_out_once,
        "同服务多实例发现与逐实例广播",
    )
    await tester.test(_test_startup_ready_and_welcome_are_mutual, "启动 ready/welcome 信号双向辨认")
    await tester.test(_test_typed_signal_gathers_independent_acknowledgements, "强类型信号逐实例 ACK 汇总")
    await tester.test(_test_signal_failure_is_isolated_per_target, "单个广播目标失败不影响其它实例 ACK")
    await tester.test(
        _test_service_target_remains_anycast_for_load_balancing,
        "服务地址维持竞争消费负载均衡",
    )
    await tester.test(
        _test_service_route_is_stable_and_distributes_routing_keys,
        "稳定路由按键分布到同服务多实例",
    )
    await tester.test(_test_draining_instance_is_removed_from_new_delivery_snapshots, "关闭实例先摘流再清理")
    await tester.test(_test_maintenance_temporarily_removes_instance_from_stable_routes, "维护窗口临时摘流并恢复")
    await tester.test(_test_fetched_session_metadata_matches_authoritative_route, "主动会话元数据与权威实例路由一致")
    await tester.test(_test_authoritative_registry_rejects_stale_alive_entry, "权威注册表拒绝本地缓存幽灵实例")
    await tester.test(
        _test_unleased_cache_is_not_routable,
        "无租约本地缓存不可参与路由",
    )
    await tester.test(_test_route_resolution_obeys_rpc_deadline, "稳定路由查询计入 RPC deadline")
    await tester.test(
        _test_expired_instance_is_removed_and_direct_waiter_is_released,
        "租约过期释放实例直投任务",
    )
    return tester
