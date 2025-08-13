from typing import TYPE_CHECKING

from core.exports import add_export

if TYPE_CHECKING:
    from core.builtins.session.internal import MessageSession


class ExecutionLockList:
    """
    执行锁。
    """

    _list = set()

    @staticmethod
    def add(msg: "MessageSession"):
        target_id = msg.session_info.sender_id
        ExecutionLockList._list.add(target_id)

    @staticmethod
    def remove(msg: "MessageSession"):
        target_id = msg.session_info.sender_id
        if target_id in ExecutionLockList._list:
            ExecutionLockList._list.remove(target_id)

    @staticmethod
    def check(msg: "MessageSession"):
        target_id = msg.session_info.sender_id
        return target_id in ExecutionLockList._list

    @staticmethod
    def get():
        return ExecutionLockList._list


add_export(ExecutionLockList)

__all__ = ["ExecutionLockList"]
