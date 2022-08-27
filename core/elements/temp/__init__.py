from core.elements import MessageSession


class ExecutionLockList:
    _list = set()

    @staticmethod
    def add(msg: MessageSession):
        targetId = msg.target.senderId
        ExecutionLockList._list.add(targetId)

    @staticmethod
    def remove(msg: MessageSession):
        targetId = msg.target.senderId
        if targetId in ExecutionLockList._list:
            ExecutionLockList._list.remove(targetId)

    @staticmethod
    def check(msg: MessageSession):
        targetId = msg.target.senderId
        return True if targetId in ExecutionLockList._list else False

    @staticmethod
    def get():
        return ExecutionLockList._list


__all__ = ["ExecutionLockList"]
