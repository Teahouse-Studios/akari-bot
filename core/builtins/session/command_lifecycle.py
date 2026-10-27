"""命令生命周期追踪 - 记录命令输出，并在触发消息被撤回时清理。"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.builtins.session.lock import ExecutionLockList
from core.config.base import CoreConfig
from core.constants.exceptions import ConfigOperationError
from core.logger import Logger

from core.queue.contracts import PlatformAPI

if TYPE_CHECKING:
    from core.builtins.session.info import EventInfo, SessionInfo
    from core.builtins.session.internal import MessageSession


RECALL_EVENT_NAME = "message_recalled"

# 命令结束后仍保留输出记录的时长，用于处理命令早已跑完才撤回的情形。
OUTPUT_TTL = 300
# 取消执行中的命令后，等待其完成收尾的上限。
CANCEL_WAIT = 5


def _enabled() -> bool:
    try:
        return bool(CoreConfig.command_recall_cleanup)
    except (AttributeError, ConfigOperationError):
        # 配置尚未由 pre_init 补写的只读进程按默认开启处理，避免撤回事件整体失效。
        return True


@dataclass
class CommandLifecycle:
    """一次命令执行的输出与任务记录，仅存在于 Server 进程。"""

    key: tuple[str, str, str]
    msg: "MessageSession"
    message_ids: list[str] = field(default_factory=list)
    task: asyncio.Task | None = None
    cancelled: bool = False
    active: bool = True
    expires_at: float = 0.0

    @property
    def session_info(self) -> "SessionInfo":
        return self.msg.session_info


class CommandLifecycleRegistry:
    """按触发消息索引命令执行状态，供撤回事件取消任务并删除输出。"""

    _by_trigger: dict[tuple[str, str, str], CommandLifecycle] = {}
    _by_task: dict[asyncio.Task, CommandLifecycle] = {}

    @staticmethod
    def _trigger_key(session_info: "SessionInfo") -> tuple[str, str, str] | None:
        if not session_info.message_id or not session_info.target_id:
            return None
        return (session_info.client_name or "", session_info.target_id, str(session_info.message_id))

    @classmethod
    def attach(cls, msg: "MessageSession") -> CommandLifecycle | None:
        """在命令或正则即将执行时登记当前任务。"""
        if not _enabled():
            return None
        task = asyncio.current_task()
        if task is not None:
            existing = cls._by_task.get(task)
            if existing is not None and existing.active:
                return existing
        key = cls._trigger_key(msg.session_info)
        if key is None:
            return None
        cls._prune()
        previous = cls._by_trigger.get(key)
        if previous is not None and previous.task is not None:
            cls._by_task.pop(previous.task, None)
        entry = CommandLifecycle(key=key, msg=msg, task=task)
        cls._by_trigger[key] = entry
        if task is not None:
            cls._by_task[task] = entry
        ExecutionLockList.state(msg).command_entry = entry
        return entry

    @classmethod
    def _entry_for(cls, msg: "MessageSession") -> CommandLifecycle | None:
        state = ExecutionLockList.try_state(msg)
        if state is None:
            return None
        entry = state.command_entry
        return entry if isinstance(entry, CommandLifecycle) else None

    @classmethod
    def record_output(cls, msg: "MessageSession", message_ids: list | str | int | None) -> None:
        """记录本次命令实际发出的平台消息 ID。"""
        entry = cls._entry_for(msg)
        if entry is None or not entry.active or message_ids is None:
            return
        ids = message_ids if isinstance(message_ids, list) else [message_ids]
        for message_id in ids:
            value = str(message_id)
            if value and value not in entry.message_ids:
                entry.message_ids.append(value)

    @classmethod
    def output_blocked(cls, msg: "MessageSession") -> bool:
        """取消后拒绝继续发送，避免撤回后又出现新的输出。"""
        entry = cls._entry_for(msg)
        return bool(entry is not None and entry.cancelled)

    @classmethod
    def finish(cls, msg: "MessageSession") -> None:
        """命令执行结束：停止追踪任务，有输出者保留至过期。"""
        task = asyncio.current_task()
        entry = cls._by_task.pop(task, None) if task is not None else None
        if entry is None:
            return
        entry.active = False
        entry.task = None
        if entry.message_ids and _enabled():
            entry.expires_at = time.monotonic() + OUTPUT_TTL
        else:
            cls._by_trigger.pop(entry.key, None)
        state = ExecutionLockList.try_state(msg)
        if state is not None and state.command_entry is entry:
            state.command_entry = None

    @classmethod
    async def handle_message_recall(cls, event_info: "EventInfo") -> bool:
        """处理撤回事件：终止执行中的命令并删除已记录的输出。"""
        if event_info.event_name != RECALL_EVENT_NAME or not _enabled():
            return False
        try:
            cls._prune()
            message_id = str(event_info.data.get("message_id") or "")
            if not message_id or not event_info.target_id:
                return False
            key = (event_info.client_name or "", event_info.target_id, message_id)
            entry = cls._by_trigger.get(key)
            if entry is None:
                return False
            operator_id = event_info.data.get("operator_id")
            if operator_id and entry.session_info.sender_id and operator_id != entry.session_info.sender_id:
                return False
            cls._by_trigger.pop(key, None)
            entry.cancelled = True
            await cls._cancel_entry(entry)
            await cls._delete_outputs(entry)
            return True
        except Exception:
            Logger.exception("Failed to handle message recall.")
            return False

    @classmethod
    async def _cancel_entry(cls, entry: CommandLifecycle) -> None:
        task = entry.task
        if task is None or task.done():
            return
        task.cancel()
        try:
            _done, pending = await asyncio.wait({task}, timeout=CANCEL_WAIT)
        except Exception:
            Logger.exception("Failed to wait for the cancelled command task.")
            return
        if pending:
            Logger.warning("Command task did not stop within the recall wait window.")

    @classmethod
    async def _delete_outputs(cls, entry: CommandLifecycle) -> None:
        message_ids = list(entry.message_ids)
        if not message_ids:
            return
        if not entry.session_info.support_delete:
            Logger.info("Platform does not support deleting messages; skipped recall cleanup.")
            return
        try:
            await PlatformAPI.delete_message.submit(entry.session_info, message_ids)
        except Exception:
            Logger.exception("Failed to delete outputs of the recalled command.")

    @classmethod
    def _prune(cls) -> None:
        now = time.monotonic()
        for key, entry in list(cls._by_trigger.items()):
            if entry.expires_at and entry.expires_at <= now:
                cls._by_trigger.pop(key, None)
            elif entry.task is not None and entry.task.done():
                # 收尾 hook 未执行（如模块被停用）时兜底清理，避免任务索引滞留。
                cls._by_task.pop(entry.task, None)
                cls._by_trigger.pop(key, None)

    @classmethod
    def clear(cls) -> None:
        """测试用：清空全部记录。"""
        cls._by_trigger.clear()
        cls._by_task.clear()


__all__ = ["CommandLifecycle", "CommandLifecycleRegistry", "RECALL_EVENT_NAME"]
