"""用于验证 JobQueue 契约的进程内后端。

该实现不属于生产配置选项。它使运行时测试能够在完全不访问 JobQueue ORM 表的情况下
覆盖 RPC、信号、实例发现和失效传播，从而避免新的传输实现再次引入数据库耦合。
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .peer import PeerIdentity, PeerRecord, PeerRegistryBase, PeerSelector, PeerState
from .transport import BatchSendResult, PROTOCOL_VERSION, RpcRequest, RpcResponse


@dataclass
class _MemoryDelivery:
    request: RpcRequest
    status: str = "pending"
    claimed_by: str | None = None


class InMemoryBroker:
    """由同一测试集群中的多个内存后端实例共享的权威状态。"""

    def __init__(self):
        import asyncio

        self.lock = asyncio.Lock()
        self.deliveries: dict[str, _MemoryDelivery] = {}
        self.responses: dict[str, RpcResponse] = {}
        self.peers: dict[str, PeerRecord] = {}

    def _fail_peer_deliveries_locked(self, peer_id: str, message: str) -> None:
        envelope = {
            "rpc": PROTOCOL_VERSION,
            "error": {"code": "unavailable", "type": "RpcUnavailableError", "message": message},
        }
        for task_id, delivery in list(self.deliveries.items()):
            if not (
                (delivery.status == "pending" and delivery.request.target == peer_id)
                or (delivery.status == "processing" and delivery.claimed_by == peer_id)
            ):
                continue
            del self.deliveries[task_id]
            if delivery.request.expects_response:
                self.responses[task_id] = RpcResponse(task_id, "failed", envelope)


class InMemoryMessageTransport:
    def __init__(self, broker: InMemoryBroker):
        self.broker = broker

    async def send(self, request: RpcRequest) -> None:
        async with self.broker.lock:
            if request.task_id in self.broker.deliveries or request.task_id in self.broker.responses:
                raise ValueError(f"Duplicate JobQueue task ID: {request.task_id}")
            self.broker.deliveries[request.task_id] = _MemoryDelivery(request)

    async def send_many(self, requests: list[RpcRequest]) -> BatchSendResult:
        accepted = set()
        rejected = {}
        seen = set()
        duplicates = set()
        for request in requests:
            if request.task_id in seen:
                duplicates.add(request.task_id)
            seen.add(request.task_id)
        async with self.broker.lock:
            for request in requests:
                if (
                    request.task_id in duplicates
                    or request.task_id in self.broker.deliveries
                    or request.task_id in self.broker.responses
                ):
                    rejected[request.task_id] = "Duplicate JobQueue task ID."
                    continue
                self.broker.deliveries[request.task_id] = _MemoryDelivery(request)
                accepted.add(request.task_id)
        return BatchSendResult(frozenset(accepted), rejected)

    async def receive(self, targets: list[str], peer_id: str | None = None) -> list[RpcRequest]:
        target_set = set(targets)
        requests = []
        async with self.broker.lock:
            for delivery in self.broker.deliveries.values():
                if delivery.status != "pending" or delivery.request.target not in target_set:
                    continue
                delivery.status = "processing"
                delivery.claimed_by = peer_id
                requests.append(delivery.request)
        return requests

    async def consume_responses(self, task_ids: list[str]) -> list[RpcResponse]:
        responses = []
        async with self.broker.lock:
            for task_id in task_ids:
                response = self.broker.responses.pop(task_id, None)
                if response is not None:
                    responses.append(response)
        return responses

    async def abandon(self, task_ids: list[str]) -> None:
        async with self.broker.lock:
            for task_id in task_ids:
                self.broker.deliveries.pop(task_id, None)
                self.broker.responses.pop(task_id, None)

    async def respond(self, request: RpcRequest, response: RpcResponse) -> None:
        if request.task_id != response.task_id:
            raise ValueError("RPC response task ID does not match its request")
        async with self.broker.lock:
            delivery = self.broker.deliveries.get(request.task_id)
            if delivery is None or delivery.status != "processing":
                return
            del self.broker.deliveries[request.task_id]
            if request.expects_response:
                self.broker.responses[request.task_id] = response


class InMemoryPeerRegistry(PeerRegistryBase):
    LEASE_SECONDS = 45
    MAINTENANCE_LEASE_SECONDS = 600
    STOPPED_RETENTION_SECONDS = 86400

    def __init__(self, broker: InMemoryBroker):
        self.broker = broker

    @staticmethod
    def _record(identity: PeerIdentity, state: PeerState, lease_seconds: int) -> PeerRecord:
        return PeerRecord(
            peer_id=identity.peer_id,
            node_id=identity.node_id,
            role=identity.role,
            service=identity.service,
            state=state,
            capabilities=identity.capabilities,
            metadata=dict(identity.metadata),
            lease_until=datetime.now(UTC) + timedelta(seconds=lease_seconds),
        )

    async def register(self, identity: PeerIdentity, state: PeerState = "starting") -> PeerRecord:
        record = self._record(identity, state, self.LEASE_SECONDS)
        async with self.broker.lock:
            self.broker.peers[identity.peer_id] = record
        return record

    async def renew(self, identity: PeerIdentity) -> bool:
        async with self.broker.lock:
            current = self.broker.peers.get(identity.peer_id)
            if current is None or current.state not in ("starting", "ready"):
                return False
            self.broker.peers[identity.peer_id] = self._record(identity, "ready", self.LEASE_SECONDS)
        return True

    async def set_state(self, peer_id: str, state: PeerState, lease_seconds: int | None = None) -> bool:
        async with self.broker.lock:
            current = self.broker.peers.get(peer_id)
            if current is None:
                return False
            self.broker.peers[peer_id] = PeerRecord(
                peer_id=current.peer_id,
                node_id=current.node_id,
                role=current.role,
                service=current.service,
                state=state,
                capabilities=current.capabilities,
                metadata=dict(current.metadata),
                lease_until=datetime.now(UTC) + timedelta(seconds=lease_seconds or self.LEASE_SECONDS),
            )
        return True

    async def unregister(self, peer_id: str) -> bool:
        async with self.broker.lock:
            current = self.broker.peers.get(peer_id)
            if current is None:
                return False
            now = datetime.now(UTC)
            self.broker.peers[peer_id] = PeerRecord(
                peer_id=current.peer_id,
                node_id=current.node_id,
                role=current.role,
                service=current.service,
                state="stopped",
                capabilities=current.capabilities,
                metadata=dict(current.metadata),
                lease_until=now,
            )
            self.broker._fail_peer_deliveries_locked(
                peer_id,
                "Target process stopped before completing the request.",
            )
        return True

    async def lookup(self, peer_id: str) -> PeerRecord | None:
        async with self.broker.lock:
            return self.broker.peers.get(peer_id)

    async def expire_stale(self) -> list[str]:
        now = datetime.now(UTC)
        expired = []
        async with self.broker.lock:
            for peer_id, current in list(self.broker.peers.items()):
                if current.state in ("starting", "ready", "maintenance", "draining") and current.lease_until <= now:
                    self.broker.peers[peer_id] = PeerRecord(
                        peer_id=current.peer_id,
                        node_id=current.node_id,
                        role=current.role,
                        service=current.service,
                        state="stopped",
                        capabilities=current.capabilities,
                        metadata=dict(current.metadata),
                        lease_until=current.lease_until,
                    )
                    self.broker._fail_peer_deliveries_locked(peer_id, "Target process lease expired.")
                    expired.append(peer_id)
            retention = now - timedelta(seconds=self.STOPPED_RETENTION_SECONDS)
            for peer_id, current in list(self.broker.peers.items()):
                if current.state == "stopped" and current.lease_until < retention:
                    del self.broker.peers[peer_id]
        return expired

    async def resolve(self, selector: PeerSelector | None = None) -> list[PeerRecord]:
        selector = selector or PeerSelector.all()
        now = datetime.now(UTC)
        required_capabilities = set(selector.capabilities)
        async with self.broker.lock:
            records = [
                record
                for record in self.broker.peers.values()
                if record.state == "ready"
                and record.lease_until > now
                and (not selector.peer_ids or record.peer_id in selector.peer_ids)
                and (not selector.node_ids or record.node_id in selector.node_ids)
                and (not selector.roles or record.role in selector.roles)
                and (not selector.services or record.service in selector.services)
                and record.peer_id not in selector.exclude_peer_ids
                and (not required_capabilities or required_capabilities.issubset(record.capabilities))
            ]
        return sorted(records, key=lambda record: record.peer_id)


class InMemoryJobQueueBackend:
    name = "memory"

    def __init__(self, broker: InMemoryBroker | None = None):
        self.broker = broker or InMemoryBroker()
        self.transport = InMemoryMessageTransport(self.broker)
        self.registry = InMemoryPeerRegistry(self.broker)
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    async def start(self, identity: PeerIdentity | None) -> None:
        self._ready = True

    async def close(self) -> None:
        self._ready = False
