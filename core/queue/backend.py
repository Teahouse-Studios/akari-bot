"""JobQueue 后端组合与配置工厂。"""

from typing import Protocol

from .peer import PeerIdentity, PeerRegistry
from .transport import MessageTransport


class JobQueueBackend(Protocol):
    name: str
    registry: PeerRegistry
    transport: MessageTransport

    @property
    def ready(self) -> bool: ...

    async def start(self, identity: PeerIdentity | None) -> None: ...

    async def close(self) -> None: ...


def create_jobqueue_backend(name: str | None = None) -> JobQueueBackend:
    """按照配置选择一套完整后端，不允许控制面和数据面交叉组合。"""
    if name is None:
        from core.config.jobqueue import JobQueueConfig

        name = JobQueueConfig.jobqueue_backend
    if not isinstance(name, str) or not name.strip():
        raise ValueError("JobQueue backend must be a nonempty string")
    backend_name = name.strip().lower()
    if backend_name == "database":
        from .database import DatabaseJobQueueBackend

        return DatabaseJobQueueBackend()
    if backend_name == "websocket":
        from .websocket import WebSocketJobQueueBackend

        return WebSocketJobQueueBackend.from_config()
    raise ValueError(f"Unsupported JobQueue backend: {name}")
