"""介质无关的 JobQueue Peer 身份、筛选条件及注册表协议。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, Protocol

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
    """选择当前处于 ready 状态且满足全部约束的进程实例。"""

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
    """以 Rendezvous Hash 将业务键稳定路由至一个 ready 实例。"""

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
    errors: dict[str, str] = field(default_factory=dict)
    unknown: tuple[str, ...] = ()


@dataclass(frozen=True)
class SignalReport:
    event_id: str
    results: dict[str, object]
    errors: dict[str, str]


class PeerRegistry(Protocol):
    MAINTENANCE_LEASE_SECONDS: int

    async def register(self, identity: PeerIdentity, state: PeerState = "starting") -> PeerRecord: ...

    async def renew(self, identity: PeerIdentity) -> bool: ...

    async def set_state(self, peer_id: str, state: PeerState, lease_seconds: int | None = None) -> bool: ...

    async def unregister(self, peer_id: str) -> bool: ...

    async def lookup(self, peer_id: str) -> PeerRecord | None: ...

    async def expire_stale(self) -> list[str]: ...

    async def resolve(self, selector: PeerSelector | None = None) -> list[PeerRecord]: ...

    async def select_route(self, route: ServiceRoute) -> PeerRecord | None: ...


class PeerRegistryBase:
    """供不同介质复用稳定路由算法的注册表基类。"""

    async def resolve(self, selector: PeerSelector | None = None) -> list[PeerRecord]:
        raise NotImplementedError

    async def select_route(self, route: ServiceRoute) -> PeerRecord | None:
        peers = await self.resolve(
            PeerSelector(
                roles=(route.role,) if route.role else (),
                services=(route.service,),
            )
        )
        if not peers:
            return None
        return max(peers, key=lambda peer: sha256(f"{route.routing_key}\0{peer.peer_id}".encode()).digest())
