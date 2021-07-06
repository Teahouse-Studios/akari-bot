from enum import Enum
from typing import Coroutine, Any, Optional
from pydantic import BaseModel
from pydantic.fields import Field


class Target(BaseModel):
    id: int
    senderId: int
    name: str
    target_from: str


class Plugin:
    def __init__(self, function, name):
        self.name = name
        self.function = function
