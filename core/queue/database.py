"""JobQueue 的数据库后端实现。

本模块是队列运行时中唯一了解 JobQueue ORM 表、事务和原子领取语义的层。
"""

from datetime import UTC, datetime, timedelta

from tortoise.transactions import in_transaction

from core.database.models import JobQueuePeersTable, JobQueuesTable
from core.logger import Logger
from .peer import PeerIdentity, PeerRecord, PeerRegistryBase, PeerSelector, PeerState
from .transport import BatchSendResult, PROTOCOL_VERSION, RpcRequest, RpcResponse


def _peer_record(row: JobQueuePeersTable) -> PeerRecord:
    return PeerRecord(
        peer_id=row.peer_id,
        node_id=row.node_id,
        role=row.role,
        service=row.service,
        state=row.state,
        capabilities=tuple(row.capabilities or []),
        metadata=dict(row.metadata or {}),
        lease_until=row.lease_until,
    )


class DatabaseMessageTransport:
    """通过 ``JobQueuesTable`` 传递请求与响应。"""

    # SQLite 只能同时执行一个写事务。限制单轮候选数量可避免积压时一次轮询
    # 对全部记录连续执行领取 UPDATE，并为业务表写入留下获得写锁的机会。
    CLAIM_BATCH_SIZE = 100

    @staticmethod
    def _row(request: RpcRequest) -> JobQueuesTable:
        return JobQueuesTable(
            task_id=request.task_id,
            correlation_id=request.correlation_id,
            source_peer_id=request.source_peer_id,
            target_peer=request.target,
            message_kind=request.message_kind,
            expects_response=request.expects_response,
            action=request.method,
            args={"rpc": request.version, "payload": request.payload, "deadline": request.deadline},
        )

    async def send(self, request: RpcRequest) -> None:
        await self._row(request).save(force_create=True)

    async def send_many(self, requests: list[RpcRequest]) -> BatchSendResult:
        if requests:
            await JobQueuesTable.bulk_create([self._row(request) for request in requests])
        return BatchSendResult.accepted_all(requests)

    async def receive(self, targets: list[str], peer_id: str | None = None) -> list[RpcRequest]:
        requests = []
        for row in await JobQueuesTable.get_all(targets, limit=self.CLAIM_BATCH_SIZE):
            if not await row.claim(peer_id):
                continue
            envelope = row.args if isinstance(row.args, dict) else {}
            requests.append(
                RpcRequest(
                    str(row.task_id),
                    row.target_peer,
                    row.action,
                    envelope.get("payload"),
                    envelope.get("deadline"),
                    version=envelope.get("rpc", 0),
                    source_peer_id=row.source_peer_id,
                    correlation_id=str(row.correlation_id) if row.correlation_id else None,
                    message_kind=row.message_kind,
                    expects_response=row.expects_response,
                )
            )
        return requests

    async def consume_responses(self, task_ids: list[str]) -> list[RpcResponse]:
        """读取并删除调用方已经能够接收的终态结果。"""
        if not task_ids:
            return []
        rows = await JobQueuesTable.filter(task_id__in=task_ids).exclude(status__in=["pending", "processing"])
        responses = [RpcResponse(str(row.task_id), row.status, row.result) for row in rows]
        if rows:
            try:
                await (
                    JobQueuesTable.filter(task_id__in=[row.task_id for row in rows])
                    .exclude(status__in=["pending", "processing"])
                    .delete()
                )
            except Exception:
                Logger.exception(f"Failed to delete {len(rows)} consumed RPC responses.")
        return responses

    async def abandon(self, task_ids: list[str]) -> None:
        """尽力清理调用方已放弃的状态，不承诺取消远端处理器。"""
        if task_ids:
            await JobQueuesTable.filter(task_id__in=task_ids).delete()

    async def respond(self, request: RpcRequest, response: RpcResponse) -> None:
        if request.task_id != response.task_id:
            raise ValueError("RPC response task ID does not match its request")
        if request.expects_response is False:
            await JobQueuesTable.filter(task_id=response.task_id, status="processing").delete()
            return
        await JobQueuesTable.filter(task_id=response.task_id, status="processing").update(
            status=response.status, result=response.envelope
        )

    async def fail_peer_deliveries(self, peer_id: str, message: str, *, connection=None) -> None:
        """在数据库后端内部终结发往失效实例的投递。"""
        result = {
            "rpc": PROTOCOL_VERSION,
            "error": {"code": "unavailable", "type": "RpcUnavailableError", "message": message},
        }

        async def fail_deliveries(db) -> None:
            await (
                JobQueuesTable.filter(target_peer=peer_id, status="pending", expects_response=False)
                .using_db(db)
                .delete()
            )
            await (
                JobQueuesTable.filter(claimed_by=peer_id, status="processing", expects_response=False)
                .using_db(db)
                .delete()
            )
            await (
                JobQueuesTable.filter(target_peer=peer_id, status="pending", expects_response=True)
                .using_db(db)
                .update(status="failed", result=result)
            )
            await (
                JobQueuesTable.filter(claimed_by=peer_id, status="processing", expects_response=True)
                .using_db(db)
                .update(status="failed", result=result)
            )

        if connection is not None:
            await fail_deliveries(connection)
            return
        async with in_transaction(JobQueuesTable._meta.default_connection) as transaction:
            await fail_deliveries(transaction)


class DatabasePeerRegistry(PeerRegistryBase):
    """通过 ``JobQueuePeersTable`` 提供权威 Peer 目录。"""

    LEASE_SECONDS = 45
    MAINTENANCE_LEASE_SECONDS = 600
    STOPPED_RETENTION_SECONDS = 86400

    def __init__(self, transport: DatabaseMessageTransport):
        self.transport = transport

    async def register(self, identity: PeerIdentity, state: PeerState = "starting") -> PeerRecord:
        now = datetime.now(UTC)
        row, _ = await JobQueuePeersTable.update_or_create(
            peer_id=identity.peer_id,
            defaults={
                "node_id": identity.node_id,
                "role": identity.role,
                "service": identity.service,
                "state": state,
                "capabilities": list(identity.capabilities),
                "metadata": identity.metadata,
                "heartbeat_at": now,
                "lease_until": now + timedelta(seconds=self.LEASE_SECONDS),
            },
        )
        return _peer_record(row)

    async def renew(self, identity: PeerIdentity) -> bool:
        now = datetime.now(UTC)
        updated = await JobQueuePeersTable.filter(
            peer_id=identity.peer_id,
            state__in=["starting", "ready"],
        ).update(
            node_id=identity.node_id,
            role=identity.role,
            service=identity.service,
            state="ready",
            capabilities=list(identity.capabilities),
            metadata=identity.metadata,
            heartbeat_at=now,
            lease_until=now + timedelta(seconds=self.LEASE_SECONDS),
        )
        return bool(updated)

    async def set_state(self, peer_id: str, state: PeerState, lease_seconds: int | None = None) -> bool:
        lease_until = datetime.now(UTC) + timedelta(seconds=lease_seconds or self.LEASE_SECONDS)
        updated = await JobQueuePeersTable.filter(peer_id=peer_id).update(state=state, lease_until=lease_until)
        return bool(updated)

    async def unregister(self, peer_id: str) -> bool:
        now = datetime.now(UTC)
        async with in_transaction(JobQueuePeersTable._meta.default_connection) as connection:
            updated = await (
                JobQueuePeersTable.filter(peer_id=peer_id)
                .using_db(connection)
                .update(state="stopped", heartbeat_at=now, lease_until=now)
            )
            if updated:
                await self.transport.fail_peer_deliveries(
                    peer_id,
                    "Target process stopped before completing the request.",
                    connection=connection,
                )
        return bool(updated)

    async def lookup(self, peer_id: str) -> PeerRecord | None:
        row = await JobQueuePeersTable.filter(peer_id=peer_id).first()
        return _peer_record(row) if row is not None else None

    async def expire_stale(self) -> list[str]:
        now = datetime.now(UTC)
        rows = await JobQueuePeersTable.filter(
            state__in=["starting", "ready", "maintenance", "draining"], lease_until__lte=now
        ).all()
        peer_ids = []
        for row in rows:
            async with in_transaction(JobQueuePeersTable._meta.default_connection) as connection:
                updated = await (
                    JobQueuePeersTable.filter(
                        peer_id=row.peer_id,
                        state__in=["starting", "ready", "maintenance", "draining"],
                        lease_until__lte=now,
                    )
                    .using_db(connection)
                    .update(state="stopped")
                )
                if updated:
                    await self.transport.fail_peer_deliveries(
                        row.peer_id,
                        "Target process lease expired.",
                        connection=connection,
                    )
                    peer_ids.append(row.peer_id)
        await JobQueuePeersTable.filter(
            state="stopped", heartbeat_at__lt=now - timedelta(seconds=self.STOPPED_RETENTION_SECONDS)
        ).delete()
        return peer_ids

    async def resolve(self, selector: PeerSelector | None = None) -> list[PeerRecord]:
        selector = selector or PeerSelector.all()
        query = JobQueuePeersTable.filter(state="ready", lease_until__gt=datetime.now(UTC))
        if selector.peer_ids:
            query = query.filter(peer_id__in=selector.peer_ids)
        if selector.node_ids:
            query = query.filter(node_id__in=selector.node_ids)
        if selector.roles:
            query = query.filter(role__in=selector.roles)
        if selector.services:
            query = query.filter(service__in=selector.services)
        if selector.exclude_peer_ids:
            query = query.exclude(peer_id__in=selector.exclude_peer_ids)
        rows = await query.all()
        required_capabilities = set(selector.capabilities)
        records = []
        for row in rows:
            if required_capabilities and not required_capabilities.issubset(set(row.capabilities or [])):
                continue
            records.append(_peer_record(row))
        records.sort(key=lambda peer: peer.peer_id)
        return records


class DatabaseJobQueueBackend:
    name = "database"

    def __init__(self):
        self.transport = DatabaseMessageTransport()
        self.registry = DatabasePeerRegistry(self.transport)
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    async def start(self, identity: PeerIdentity | None) -> None:
        self._ready = True

    async def close(self) -> None:
        self._ready = False


# 旧名称仅作为数据库实现的导入兼容层保留。
DatabaseTransport = DatabaseMessageTransport
