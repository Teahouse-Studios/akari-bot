"""介质无关的 JobQueue 数据面协议。

传输实现只负责请求、响应及本地放弃状态的传递，不负责业务参数编解码或
处理器分发。取消本地等待不等同于撤销已经开始的远端副作用。
"""

from dataclasses import dataclass, field
from typing import Protocol

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

PROTOCOL_VERSION = 2
DEFAULT_TIMEOUT_SECONDS = 7200


@dataclass(frozen=True)
class RpcRequest:
    task_id: str
    target: str
    method: str
    payload: JsonValue
    deadline: float
    version: int = PROTOCOL_VERSION
    source_peer_id: str | None = None
    correlation_id: str | None = None
    message_kind: str = "rpc"
    expects_response: bool = True


@dataclass(frozen=True)
class RpcResponse:
    task_id: str
    status: str
    envelope: JsonValue


@dataclass(frozen=True)
class BatchSendResult:
    """逐项描述批量投递结果，避免将部分成功误判为原子失败。"""

    accepted: frozenset[str] = frozenset()
    rejected: dict[str, str] = field(default_factory=dict)
    unknown: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        accepted = frozenset(self.accepted)
        rejected = dict(self.rejected)
        unknown = frozenset(self.unknown)
        if accepted & rejected.keys() or accepted & unknown or rejected.keys() & unknown:
            raise ValueError("Batch delivery result groups must be disjoint")
        if any(not isinstance(task_id, str) or not task_id for task_id in (*accepted, *rejected, *unknown)):
            raise ValueError("Batch delivery result contains an invalid task ID")
        if any(not isinstance(reason, str) or not reason for reason in rejected.values()):
            raise ValueError("Rejected batch deliveries require a nonempty reason")
        object.__setattr__(self, "accepted", accepted)
        object.__setattr__(self, "rejected", rejected)
        object.__setattr__(self, "unknown", unknown)

    @classmethod
    def accepted_all(cls, requests: list[RpcRequest]) -> "BatchSendResult":
        return cls(accepted=frozenset(request.task_id for request in requests))


class MessageTransport(Protocol):
    async def send(self, request: RpcRequest) -> None: ...

    async def send_many(self, requests: list[RpcRequest]) -> BatchSendResult: ...

    async def receive(self, targets: list[str], peer_id: str | None = None) -> list[RpcRequest]: ...

    async def consume_responses(self, task_ids: list[str]) -> list[RpcResponse]: ...

    async def abandon(self, task_ids: list[str]) -> None: ...

    async def respond(self, request: RpcRequest, response: RpcResponse) -> None: ...


# 兼容现有扩展的类型名称；新实现应使用 MessageTransport。
RpcTransport = MessageTransport
