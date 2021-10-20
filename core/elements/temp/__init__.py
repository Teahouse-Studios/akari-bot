from typing import Union


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




__all__ = ["EnabledModulesCache", "SenderInfoCache"]
