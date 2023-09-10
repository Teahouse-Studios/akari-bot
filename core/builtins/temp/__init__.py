from core.types import MessageSession


class Temp:
    data = {}


class ExecutionLockList:
    _list = set()

    @staticmethod
    def add(msg: MessageSession):
        target_id = msg.target.sender_id
        ExecutionLockList._list.add(target_id)

    @staticmethod
    def remove(msg: MessageSession):
        target_id = msg.target.sender_id
        if target_id in ExecutionLockList._list:
            ExecutionLockList._list.remove(target_id)

    @staticmethod
    def check(msg: MessageSession):
        target_id = msg.target.sender_id
        return True if target_id in ExecutionLockList._list else False

    @staticmethod
    def get():
        return ExecutionLockList._list


__all__ = ["Temp", "ExecutionLockList"]
