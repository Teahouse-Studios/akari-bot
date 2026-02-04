import asyncio
import threading
import time
from typing import Any, ClassVar


class TokenBucket:
    def __init__(self, capacity: int, refill_interval: int):
        self.capacity = capacity
        self.rate = capacity / float(refill_interval) if refill_interval > 0 else capacity
        self.tokens = float(capacity)
        self.ts = time.time()

    def _refill(self):
        now = time.time()
        self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
        self.ts = now

    def consume(self, amount: int = 1) -> bool:
        now = time.time()
        self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
        self.ts = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def peek(self) -> float:
        now = time.time()
        return min(self.capacity, self.tokens + (now - self.ts) * self.rate)

    def wait_time(self, amount: int = 1) -> float:
        self._refill()
        if self.tokens >= amount:
            return 0.0
        return (amount - self.tokens) / self.rate

    def refill(self, amount: int | float = 1):
        self._refill()
        self.tokens = min(self.capacity, self.tokens + amount)

    def __repr__(self):
        return f"{self.__class__.__name__}(capacity={self.capacity}, tokens={self.peek():.2f}, rate={self.rate:.2f}/s)"

    def __bool__(self):
        return self.peek() > 0


class ExpiringTempDict:
    __slots__ = ("exp", "ts", "data", "_lock")

    _registry: ClassVar[list] = []
    _registry_lock: ClassVar[threading.Lock] = threading.Lock()
    _clear_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, exp: int | float = 86400.0, ts: int | float = time.time(), data: Any = None, root: bool = True):
        self.exp = exp
        self.ts = float(ts)
        self.data = data or {}
        self._lock = threading.RLock()
        if root:
            with self._registry_lock:
                self._registry.append(self)

    def __reversed__(self):
        return reversed(self.data)

    def __iter__(self):
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, key: str):
        with self._lock:
            if key not in self.data:
                self.data[key] = ExpiringTempDict(exp=self.exp, root=False)
            return self.data[key]

    def __setitem__(self, key: str, value: Any):
        with self._lock:
            self.data[key] = value

    def __delitem__(self, key: str):
        with self._lock:
            del self.data[key]

    def is_expired(self, now: float | None = None) -> bool:
        now = now or time.time()
        return (time.time() - self.ts) > self.exp

    def refresh(self):
        with self._lock:
            self.ts = time.time()

    def clear_expired(self, now: float | None = None) -> bool:
        """
        清除内部过期数据。
        返回 True 表示自身可被外层删除。
        """
        now = now or time.time()

        with self._lock:
            if not self.is_expired(now):
                to_delete = []
                for k, v in self.data.items():
                    if isinstance(v, ExpiringTempDict):
                        if v.clear_expired(now):
                            to_delete.append(k)

                for k in to_delete:
                    del self.data[k]
                return False

            return len(self.data) == 0

    @classmethod
    async def clear_all(cls):
        now = time.time()
        async with cls._clear_lock:
            objs = list(cls._registry)

            await asyncio.to_thread(cls._sync_clear_all, objs, now)

    @staticmethod
    def _sync_clear_all(objs, now):
        for obj in objs:
            try:
                obj.clear_expired(now)
            except Exception:
                pass

    def to_dict(self) -> dict:
        with self._lock:
            result = {}
            for k, v in self.data.items():
                if isinstance(v, ExpiringTempDict):
                    result[k] = v.to_dict()
                else:
                    result[k] = v
            result["_ts"] = self.ts
            result["_exp"] = self.exp
            return result

    @classmethod
    def from_dict(cls, d: dict) -> "ExpiringTempDict":
        obj = cls(ts=d.get("_ts", time.time()), exp=d.get("_exp", 86400))
        for k, v in d.items():
            if k in ("_ts", "_exp"):
                continue
            if isinstance(v, dict):
                obj.data[k] = cls.from_dict(v)
            else:
                obj.data[k] = v
        return obj

    def clear(self):
        with self._lock:
            self.data.clear()

    def copy(self):
        with self._lock:
            new_obj = ExpiringTempDict(exp=self.exp, ts=self.ts)
            for k, v in self.data.items():
                new_obj.data[k] = v.copy() if isinstance(v, ExpiringTempDict) else v
            return new_obj

    def fromkeys(self, keys, value=None):
        with self._lock:
            new_obj = ExpiringTempDict(exp=self.exp)
            for key in keys:
                new_obj.data[key] = value
            return new_obj

    def get(self, key, default=None):
        with self._lock:
            return self.data.get(key, default)

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def items(self):
        return self.data.items()

    def pop(self, key, default=None):
        with self._lock:
            return self.data.pop(key, default)

    def popitem(self):
        with self._lock:
            return self.data.popitem()

    def setdefault(self, key, default=None):
        with self._lock:
            return self.data.setdefault(key, default)

    def update(self, other=(), **kwargs):
        with self._lock:
            if isinstance(other, ExpiringTempDict):
                other = other.data
            elif isinstance(other, dict):
                pass
            else:
                other = dict(other)
            self.data.update(other)
            if kwargs:
                self.data.update(kwargs)

    def __or__(self, other: "dict | ExpiringTempDict"):
        new_obj = self.copy()
        new_obj.update(other)
        return new_obj

    def __ior__(self, other: "dict | ExpiringTempDict"):
        self.update(other)
        return self

    def __ror__(self, other: "dict | ExpiringTempDict"):
        if isinstance(other, dict):
            new_dict = other.copy()
            new_dict.update(self.to_dict())
            return new_dict
        return NotImplemented

    def __repr__(self):
        return f"{self.__class__.__name__}({self.data})"

    def __str__(self):
        return str(self.data)

    def __contains__(self, item):
        return item in self.data

    def __eq__(self, other):
        if isinstance(other, ExpiringTempDict):
            return self.data == other.data
        return self.data == other

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None

    def __bool__(self):
        return bool(self.data)

    def __getattr__(self, item):
        return getattr(self.data, item)
