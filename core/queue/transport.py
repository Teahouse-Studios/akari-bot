"""Database delivery for RPC. Only this layer knows about queue ORM rows.

Claiming is atomic, but delivery is not exactly once: if a process dies after an
external side effect, its result can be lost. Claimed requests are never retried.
The existing table and its retention policy remain usable without a migration.
"""

from dataclasses import dataclass
from typing import Protocol

from core.database.models import JobQueuesTable

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

PROTOCOL_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = JobQueuesTable.ACTIVE_TIMEOUT_SECONDS


@dataclass(frozen=True)
class RpcRequest:
    task_id: str
    target: str
    method: str
    payload: JsonValue
    deadline: float
    version: int = PROTOCOL_VERSION


@dataclass(frozen=True)
class RpcResponse:
    task_id: str
    status: str
    envelope: JsonValue


class RpcTransport(Protocol):
    async def send(self, request: RpcRequest) -> None: ...
    async def receive(self, targets: list[str]) -> list[RpcRequest]: ...
    async def responses(self, task_ids: list[str]) -> list[RpcResponse]: ...
    async def finish(self, response: RpcResponse) -> None: ...


class DatabaseTransport:
    async def send(self, request: RpcRequest) -> None:
        await JobQueuesTable.create(
            task_id=request.task_id,
            target_client=request.target,
            action=request.method,
            args={"rpc": request.version, "payload": request.payload, "deadline": request.deadline},
        )

    async def receive(self, targets: list[str]) -> list[RpcRequest]:
        requests = []
        for row in await JobQueuesTable.get_all(targets):
            if not await row.claim():
                continue
            # Invalid/old envelopes become explicit protocol errors in the runtime.
            envelope = row.args if isinstance(row.args, dict) else {}
            deadline = envelope.get("deadline")
            if not isinstance(deadline, (int, float)):
                deadline = 0
            requests.append(
                RpcRequest(
                    str(row.task_id),
                    row.target_client,
                    row.action,
                    envelope.get("payload"),
                    deadline,
                    envelope.get("rpc", 0),
                )
            )
        return requests

    async def responses(self, task_ids: list[str]) -> list[RpcResponse]:
        rows = await JobQueuesTable.filter(task_id__in=task_ids).exclude(status__in=["pending", "processing"])
        return [RpcResponse(str(row.task_id), row.status, row.result) for row in rows]

    async def finish(self, response: RpcResponse) -> None:
        # A sweeper may already have expired the request. Never overwrite a terminal
        # state with a late success and never resurrect a deleted request.
        await JobQueuesTable.filter(task_id=response.task_id, status="processing").update(
            status=response.status, result=response.envelope
        )
