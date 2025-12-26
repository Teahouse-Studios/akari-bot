import asyncio
import threading
import time
from typing import Any, ClassVar, Union, Iterable


class TempCounter:
    value = 0

    @classmethod
    def add(cls):
        cls.value += 1
        return cls.value


class TempList:
    def __init__(self, length=200, _items=None):
        self.items = _items or []
        self.length = length

    def __enter__(self):
        return self.items

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.items.clear()

    def __iter__(self):
        return iter(self.items)

    def __reversed__(self):
        return reversed(self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, item):
        return self.items[item]

    def __setitem__(self, index, value):
        self.items[index] = value

    def __delitem__(self, index):
        del self.items[index]

    def append(self, item):
        self.items.append(item)
        if len(self.items) > self.length:
            self.items.pop(0)

    def extend(self, items: Union[Iterable, "TempList"]):
        if isinstance(items, TempList):
            items = items.items
        self.items.extend(items)
        if len(self.items) > self.length:
            self.items = self.items[-self.length:]

    def insert(self, index, item):
        return self.items.insert(index, item)

    def remove(self, item):
        self.items.remove(item)

    def pop(self, index=-1):
        return self.items.pop(index)

    def clear(self):
        self.items.clear()

    def index(self, item):
        return self.items.index(item)

    def count(self, item):
        return self.items.count(item)

    def sort(self, key=None, reverse=False):
        self.items.sort(key=key, reverse=reverse)

    def reverse(self):
        self.items.reverse()

    def copy(self):
        return TempList(self.length, _items=self.items.copy())

    def __repr__(self):
        return repr(self.items)

    def __str__(self):
        return str(self.items)

    def __contains__(self, item):
        return item in self.items

    def __add__(self, other: Union[Iterable, "TempList"]):
        if isinstance(other, TempList):
            other = other.items
        new_items = self.items + other
        if len(new_items) > self.length:
            new_items = new_items[-self.length:]
        return TempList(self.length, _items=new_items)

    def __iadd__(self, other: Union[Iterable, "TempList"]):
        if isinstance(other, TempList):
            other = other.items
        self.items += other
        if len(self.items) > self.length:
            self.items = self.items[-self.length:]
        return self

    def __mul__(self, other):
        new_items = self.items * other
        if len(new_items) > self.length:
            new_items = new_items[-self.length:]
        return TempList(self.length, _items=new_items)

    def __imul__(self, other):
        self.items *= other
        if len(self.items) > self.length:
            self.items = self.items[-self.length:]
        return self

    def __eq__(self, other):
        return self.items == other

    def __ne__(self, other):
        return self.items != other

    def __lt__(self, other):
        return self.items < other

    def __le__(self, other):
        return self.items <= other

    def __gt__(self, other):
        return self.items > other

    def __ge__(self, other):
        return self.items >= other

    def __hash__(self):
        return hash(self.items)

    def __bool__(self):
        return bool(self.items)

    def __getattr__(self, item):
        return getattr(self.items, item)


class ExpiringTempDict:
    _registry: ClassVar[list] = []
    _lock: ClassVar[threading.RLock] = threading.RLock()
    _clear_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, exp: Union[int, float] = 86400.0, ts: Union[int, float] = time.time(), data: Any = None):
        self.exp = exp
        self.data = data or {}
        self.ts = float(ts)
        with self._lock:
            self.__class__._registry.append(self)

    def __reversed__(self):
        return reversed(self.data)

    def __iter__(self):
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, key: str):
        with self._lock:
            if key not in self.data:
                self.data[key] = ExpiringTempDict(exp=self.exp)
            return self.data[key]

    def __setitem__(self, key: str, value: Any):
        with self._lock:
            self.data[key] = value

    def __delitem__(self, key: str):
        with self._lock:
            del self.data[key]

    def is_expired(self) -> bool:
        with self._lock:
            return (time.time() - self.ts) > self.exp

    def refresh(self):
        with self._lock:
            self.ts = time.time()

    def clear_expired(self) -> bool:
        """
        清除内部过期数据。
        返回 True 表示自身可被外层删除。
        """
        with self._lock:
            to_delete = []
            for k, v in self.data.items():
                if isinstance(v, ExpiringTempDict):
                    should_delete = v.clear_expired()
                    if should_delete:
                        to_delete.append(k)
                else:
                    continue
            for k in to_delete:
                del self.data[k]
            if hasattr(self, "ts") and self.is_expired() and not self.data:
                return True
            return False

    async def async_clear_expired(self) -> bool:
        with self._lock:
            to_delete = []
            for k, v in self.data.items():
                if isinstance(v, ExpiringTempDict):
                    should_delete = await v.async_clear_expired()
                    if should_delete:
                        to_delete.append(k)
                else:
                    continue
            for k in to_delete:
                del self.data[k]
            if hasattr(self, "ts") and self.is_expired() and not self.data:
                return True
            return False

    @classmethod
    async def clear_all(cls):
        async with cls._clear_lock:
            for obj in cls._registry:
                await obj.async_clear_expired()

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
        with self._lock:
            return self.data.keys()

    def values(self):
        with self._lock:
            return self.data.values()

    def items(self):
        with self._lock:
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

    def __or__(self, other: Union[dict, "ExpiringTempDict"]):
        new_obj = self.copy()
        new_obj.update(other)
        return new_obj

    def __ior__(self, other: Union[dict, "ExpiringTempDict"]):
        self.update(other)
        return self

    def __ror__(self, other: Union[dict, "ExpiringTempDict"]):
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

    def __bool__(self):
        return bool(self.data)

    def __getattr__(self, item):
        return getattr(self.data, item)
