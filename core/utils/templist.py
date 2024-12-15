from typing import Union, Iterable


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

    def __len__(self):
        return len(self.items)

    def __getitem__(self, item):
        return self.items[item]

    def __setitem__(self, key, value):
        self.items[key] = value

    def append(self, item):
        self.items.append(item)
        if len(self.items) > self.length:
            self.items.pop(0)

    def extend(self, items: Union[Iterable, "TempList"]):
        if isinstance(items, TempList):
            items = items.items
        self.items.extend(items)
        if len(self.items) > self.length:
            self.items = self.items[-self.length :]

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
            new_items = new_items[-self.length :]
        return TempList(self.length, _items=new_items)

    def __iadd__(self, other: Union[Iterable, "TempList"]):
        if isinstance(other, TempList):
            other = other.items
        self.items += other
        if len(self.items) > self.length:
            self.items = self.items[-self.length :]
        return self

    def __mul__(self, other):
        new_items = self.items * other
        if len(new_items) > self.length:
            new_items = new_items[-self.length :]
        return TempList(self.length, _items=new_items)

    def __imul__(self, other):
        self.items *= other
        if len(self.items) > self.length:
            self.items = self.items[-self.length :]
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
