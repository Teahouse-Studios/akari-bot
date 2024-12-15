from typing import Any


class Param:
    def __init__(self, name: str, type_: Any = None):
        self.name = name
        self.type = type_

    def __repr__(self):
        return f"{self.name}: {self.type}"


__all__ = ["Param"]
