from enum import Enum
from typing import Optional
from pydantic import BaseModel
from pydantic.fields import Field


class Target(BaseModel):
    id: int
    senderId: int
    name: str
    target_from: str