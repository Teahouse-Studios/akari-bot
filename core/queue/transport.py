"""Database delivery for RPC. Only this layer knows about queue ORM rows.

Claiming is atomic, but delivery is not exactly once: if a process dies after an
external side effect, its result can be lost. Claimed requests are never retried.
Protocol-v2 delivery metadata is stored in the migrated queue table.
"""

from dataclasses import dataclass
from typing import Protocol

from core.database.models import JobQueuesTable
from core.logger import Logger

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

PROTOCOL_VERSION = 2
DEFAULT_TIMEOUT_SECONDS = JobQueuesTable.ACTIVE_TIMEOUT_SECONDS


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


class RpcTransport(Protocol):
    async def send(self, request: RpcRequest) -> None: ...
    async def send_many(self, requests: list[RpcRequest]) -> None: ...
    async def receive(self, targets: list[str], peer_id: str | None = None) -> list[RpcRequest]: ...
    async def consume_responses(self, task_ids: list[str]) -> list[RpcResponse]: ...
    async def discard(self, task_ids: list[str]) -> None: ...
    async def finish(self, response: RpcResponse, *, expects_response: bool = True) -> None: ...


class DatabaseTransport:
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

    async def send_many(self, requests: list[RpcRequest]) -> None:
        if requests:
            await JobQueuesTable.bulk_create([self._row(request) for request in requests])

    async def receive(self, targets: list[str], peer_id: str | None = None) -> list[RpcRequest]:
        requests = []
        for row in await JobQueuesTable.get_all(targets):
            if not await row.claim(peer_id):
                continue
            # Invalid/old envelopes become explicit protocol errors in the runtime.
            envelope = row.args if isinstance(row.args, dict) else {}
            deadline = envelope.get("deadline")
            requests.append(
                RpcRequest(
                    str(row.task_id),
                    row.target_peer,
                    row.action,
                    envelope.get("payload"),
                    deadline,
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
                # 结果已经读取到内存时，清理失败不应把可用结果降级为 unavailable，
                # 也不应使轮询器退出。遗留终态行将由定时清理兜底回收。
                Logger.exception(f"Failed to delete {len(rows)} consumed RPC responses.")
        return responses

    async def discard(self, task_ids: list[str]) -> None:
        """删除调用方已经放弃等待的任务；已开始的远端处理器不受影响。"""
        if task_ids:
            await JobQueuesTable.filter(task_id__in=task_ids).delete()

    async def finish(self, response: RpcResponse, *, expects_response: bool = True) -> None:
        # A sweeper may already have expired the request. Never overwrite a terminal
        # state with a late success and never resurrect a deleted request.
        if expects_response is False:
            await JobQueuesTable.filter(task_id=response.task_id, status="processing").delete()
            return
        await JobQueuesTable.filter(task_id=response.task_id, status="processing").update(
            status=response.status, result=response.envelope
        )
