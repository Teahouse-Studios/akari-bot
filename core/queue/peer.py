"""Shared JobQueue peer identity, discovery and selection.

The database lease registry is authoritative. Process-local topology caches are
only accelerators and are periodically reconciled from this directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Literal

from tortoise.transactions import in_transaction

from core.database.models import JobQueuePeersTable, JobQueuesTable

type PeerRole = Literal["client", "server", "worker", "test"]
type PeerState = Literal["starting", "ready", "maintenance", "draining", "stopped"]


@dataclass(frozen=True)
class PeerIdentity:
    peer_id: str
    role: str
    service: str
    node_id: str | None = None
    capabilities: tuple[str, ...] = ()
    metadata: dict = field(default_factory=dict)

    def snapshot(self, state: str = "ready") -> dict:
        return {
            "peer_id": self.peer_id,
            "node_id": self.node_id,
            "role": self.role,
            "service": self.service,
            "state": state,
            "capabilities": list(self.capabilities),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PeerSelector:
    """Select ready process instances for fan-out delivery."""

    peer_ids: tuple[str, ...] = ()
    node_ids: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    exclude_peer_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        limits = {
            "peer_ids": 128,
            "node_ids": 128,
            "roles": 32,
            "services": 128,
            "capabilities": 128,
            "exclude_peer_ids": 128,
        }
        for field_name, max_length in limits.items():
            values = getattr(self, field_name)
            if isinstance(values, str):
                raise TypeError(f"Peer selector {field_name} must be a collection of strings")
            normalized = tuple(dict.fromkeys(values))
            if any(not isinstance(value, str) or not value or len(value) > max_length for value in normalized):
                raise ValueError(f"Peer selector {field_name} contains an invalid value")
            object.__setattr__(self, field_name, normalized)

    @classmethod
    def all(cls) -> "PeerSelector":
        return cls()

    @classmethod
    def peer(cls, *peer_ids: str) -> "PeerSelector":
        return cls(peer_ids=tuple(peer_ids))

    @classmethod
    def node(cls, *node_ids: str) -> "PeerSelector":
        return cls(node_ids=tuple(node_ids))

    @classmethod
    def role(cls, *roles: str) -> "PeerSelector":
        return cls(roles=tuple(roles))

    @classmethod
    def service(cls, *services: str) -> "PeerSelector":
        return cls(services=tuple(services))

    @classmethod
    def capability(cls, *capabilities: str) -> "PeerSelector":
        return cls(capabilities=tuple(capabilities))

    def excluding(self, *peer_ids: str) -> "PeerSelector":
        return PeerSelector(
            peer_ids=self.peer_ids,
            node_ids=self.node_ids,
            roles=self.roles,
            services=self.services,
            capabilities=self.capabilities,
            exclude_peer_ids=tuple(dict.fromkeys((*self.exclude_peer_ids, *peer_ids))),
        )


@dataclass(frozen=True)
class ServiceRoute:
    """Resolve a logical service to one ready instance using rendezvous hashing."""

    service: str
    routing_key: str
    role: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.service, str) or not self.service or len(self.service) > 128:
            raise ValueError("Route service must be a nonempty string no longer than 128 characters")
        if not isinstance(self.routing_key, str):
            raise TypeError("Route key must be a string")
        if self.role is not None and (not isinstance(self.role, str) or not self.role or len(self.role) > 32):
            raise ValueError("Route role must be a nonempty string no longer than 32 characters")


@dataclass(frozen=True)
class PeerRecord:
    peer_id: str
    node_id: str | None
    role: str
    service: str
    state: str
    capabilities: tuple[str, ...]
    metadata: dict
    lease_until: datetime

    @classmethod
    def from_model(cls, row: JobQueuePeersTable) -> "PeerRecord":
        return cls(
            peer_id=row.peer_id,
            node_id=row.node_id,
            role=row.role,
            service=row.service,
            state=row.state,
            capabilities=tuple(row.capabilities or []),
            metadata=dict(row.metadata or {}),
            lease_until=row.lease_until,
        )

    def snapshot(self) -> dict:
        lease_until = self.lease_until
        if lease_until.tzinfo is None:
            lease_until = lease_until.replace(tzinfo=UTC)
        return {
            "peer_id": self.peer_id,
            "node_id": self.node_id,
            "role": self.role,
            "service": self.service,
            "state": self.state,
            "capabilities": list(self.capabilities),
            "metadata": self.metadata,
            "lease_until": lease_until.timestamp(),
        }


@dataclass(frozen=True)
class SignalContext:
    event_id: str
    source_peer_id: str | None
    target_peer_id: str


@dataclass(frozen=True)
class SignalReceipt:
    event_id: str
    deliveries: dict[str, str]


@dataclass(frozen=True)
class SignalReport:
    event_id: str
    results: dict[str, object]
    errors: dict[str, str]


class PeerDirectory:
    LEASE_SECONDS = 45
    MAINTENANCE_LEASE_SECONDS = 600
    STOPPED_RETENTION_SECONDS = 86400

    @classmethod
    async def register(cls, identity: PeerIdentity, state: PeerState = "starting") -> PeerRecord:
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
                "lease_until": now + timedelta(seconds=cls.LEASE_SECONDS),
            },
        )
        return PeerRecord.from_model(row)

    @classmethod
    async def renew(cls, identity: PeerIdentity) -> bool:
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
            lease_until=now + timedelta(seconds=cls.LEASE_SECONDS),
        )
        return bool(updated)

    @classmethod
    async def set_state(cls, peer_id: str, state: PeerState, lease_seconds: int | None = None) -> bool:
        lease_until = datetime.now(UTC) + timedelta(seconds=lease_seconds or cls.LEASE_SECONDS)
        updated = await JobQueuePeersTable.filter(peer_id=peer_id).update(state=state, lease_until=lease_until)
        return bool(updated)

    @classmethod
    async def unregister(cls, peer_id: str) -> bool:
        now = datetime.now(UTC)
        async with in_transaction(JobQueuePeersTable._meta.default_connection) as connection:
            updated = await (
                JobQueuePeersTable.filter(peer_id=peer_id)
                .using_db(connection)
                .update(state="stopped", heartbeat_at=now, lease_until=now)
            )
            if updated:
                await cls._fail_instance_deliveries(
                    peer_id,
                    "Target process stopped before completing the request.",
                    connection=connection,
                )
        return bool(updated)

    @classmethod
    async def lookup(cls, peer_id: str) -> PeerRecord | None:
        """Return the current registry row regardless of routable state."""
        row = await JobQueuePeersTable.filter(peer_id=peer_id).first()
        return PeerRecord.from_model(row) if row is not None else None

    @classmethod
    async def expire_stale(cls) -> list[str]:
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
                    await cls._fail_instance_deliveries(
                        row.peer_id,
                        "Target process lease expired.",
                        connection=connection,
                    )
                    peer_ids.append(row.peer_id)
        await JobQueuePeersTable.filter(
            state="stopped", heartbeat_at__lt=now - timedelta(seconds=cls.STOPPED_RETENTION_SECONDS)
        ).delete()
        return peer_ids

    @staticmethod
    async def _fail_instance_deliveries(peer_id: str, message: str, *, connection=None) -> None:
        from core.queue.transport import PROTOCOL_VERSION

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

    @classmethod
    async def resolve(cls, selector: PeerSelector | None = None) -> list[PeerRecord]:
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
            records.append(PeerRecord.from_model(row))
        records.sort(key=lambda peer: peer.peer_id)
        return records

    @classmethod
    async def select_route(cls, route: ServiceRoute) -> PeerRecord | None:
        peers = await cls.resolve(
            PeerSelector(
                roles=(route.role,) if route.role else (),
                services=(route.service,),
            )
        )
        if not peers:
            return None
        return max(
            peers,
            key=lambda peer: sha256(f"{route.routing_key}\0{peer.peer_id}".encode()).digest(),
        )

    @classmethod
    async def refresh_alive_cache(cls) -> list[PeerRecord]:
        expired_peer_ids = await cls.expire_stale()
        records = await cls.resolve()
        from core.alive import Alive

        for peer_id in expired_peer_ids:
            data = Alive.values.get(peer_id, {})
            Alive.refresh_peer(
                peer_id,
                str(data.get("service", "")),
                role=str(data.get("role", "client")),
                state="stopped",
                capabilities=list(data.get("capabilities", [])),
                metadata={
                    key: value
                    for key, value in data.items()
                    if key
                    not in {
                        "peer_id",
                        "client_name",
                        "service",
                        "role",
                        "state",
                        "capabilities",
                        "lease_until",
                        "ts",
                    }
                },
            )
        Alive.replace_peers(records)
        return records
