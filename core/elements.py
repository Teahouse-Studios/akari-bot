from enum import Enum
from typing import Optional
from pydantic import BaseModel
from pydantic.fields import Field


class Target(BaseModel):
    id: int
    name: str
    target_from: str