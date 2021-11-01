from typing import Union

from core.elements import MessageSession


class EnabledModulesCache:
    _cache = {}

    @staticmethod
    def add_cache(key, value):
        EnabledModulesCache._cache[key] = value

    @staticmethod
    def get_cache(key):
        return EnabledModulesCache._cache.get(key, False)


class SenderInfoCache:
    _cache = {}

    @staticmethod
    def add_cache(key, value):
        SenderInfoCache._cache[key] = value

    @staticmethod
    def get_cache(key) -> Union[dict, bool]:
        return SenderInfoCache._cache.get(key, False)


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


__all__ = ["EnabledModulesCache", "SenderInfoCache", "ExecutionLockList"]
