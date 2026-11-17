"""Process-local view of the authoritative JobQueue peer directory."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from core.builtins.converter import converter
from core.builtins.session.features import Features

if TYPE_CHECKING:
    from core.queue.peer import PeerRecord


class Alive:
    """Synchronous routing cache keyed by unique process ``peer_id``."""

    values: dict[str, dict] = {}
    _state_rank = {"starting": 0, "ready": 1, "maintenance": 2, "draining": 3, "stopped": 4}

    @classmethod
    def refresh_peer(
        cls,
        peer_id: str,
        service: str,
        role: str = "client",
        state: str = "ready",
        capabilities: list[str] | None = None,
        metadata: dict | None = None,
        lease_until: datetime | None = None,
        force: bool = False,
    ) -> None:
        current = cls.values.get(peer_id)
        if (
            not force
            and current
            and cls._state_rank.get(state, 0) < cls._state_rank.get(str(current.get("state", "ready")), 1)
        ):
            return
        data = dict(metadata or {})
        data.update(
            {
                "peer_id": peer_id,
                "client_name": service,
                "service": service,
                "role": role,
                "state": state,
                "capabilities": list(capabilities or []),
                "lease_until": lease_until,
                "ts": datetime.now(UTC),
            }
        )
        features = data.get("features")
        if isinstance(features, dict):
            try:
                data["features"] = converter.structure(features, Features)
            except Exception:
                data["features"] = None
        cls.values[peer_id] = data

    @classmethod
    def replace_peers(cls, peers: list[PeerRecord]) -> None:
        previous = cls.values
        values = {}
        for peer in peers:
            cls.refresh_peer(
                peer.peer_id,
                peer.service,
                role=peer.role,
                state=peer.state,
                capabilities=list(peer.capabilities),
                metadata=peer.metadata,
                lease_until=peer.lease_until,
                force=True,
            )
            values[peer.peer_id] = cls.values[peer.peer_id]
        now = datetime.now(UTC)
        for peer_id, data in previous.items():
            if data.get("state") not in {"draining", "stopped"} or peer_id in values:
                continue
            if (now - cls._timestamp(data)).total_seconds() < 120:
                values[peer_id] = data
        cls.values = values

    @staticmethod
    def _timestamp(data: dict) -> datetime:
        value = data.get("ts", datetime.now(UTC))
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    @classmethod
    def get_alive(cls) -> dict[str, dict]:
        now = datetime.now(UTC)
        result = {}
        for peer_id, data in cls.values.items():
            if data.get("state", "ready") != "ready":
                continue
            lease_until = data.get("lease_until")
            if lease_until is None:
                continue
            if lease_until.tzinfo is None:
                lease_until = lease_until.replace(tzinfo=UTC)
            if lease_until <= now:
                continue
            result[peer_id] = data
        return result

    @classmethod
    def is_alive(cls, identifier: str) -> bool:
        return any(
            identifier in (peer_id, data.get("service"), data.get("client_name"))
            for peer_id, data in cls.get_alive().items()
        )

    @classmethod
    def peer_ids(cls, service: str | None = None, role: str | None = None) -> list[str]:
        return sorted(
            peer_id
            for peer_id, data in cls.get_alive().items()
            if (service is None or data.get("service", peer_id) == service)
            and (role is None or data.get("role", "client") == role)
        )

    @classmethod
    def determine_target_from(cls, target_id: str):
        matches = [
            prefix
            for data in cls.get_alive().values()
            for prefix in data.get("target_prefix_list", [])
            if target_id.startswith(prefix + "|") or target_id == prefix
        ]
        return max(matches, key=len) if matches else None

    @classmethod
    def determine_sender_from(cls, sender_id: str):
        matches = [
            prefix
            for data in cls.get_alive().values()
            for prefix in data.get("sender_prefix_list", [])
            if sender_id.startswith(prefix + "|") or sender_id == prefix
        ]
        return max(matches, key=len) if matches else None

    @classmethod
    def determine_client(cls, id: str):
        candidates = []
        for peer_id, data in cls.get_alive().items():
            for prefix in data.get("target_prefix_list", []) + data.get("sender_prefix_list", []):
                if id.startswith(prefix + "|") or id == prefix:
                    candidates.append((len(prefix), data.get("service") or data.get("client_name") or peer_id))
        return max(candidates)[1] if candidates else None
