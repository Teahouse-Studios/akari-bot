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
    def __init__(self,
                 function,
                 bind_prefix,
                 alias,
                 help_doc,
                 need_self_process,
                 is_admin_function,
                 is_base_function,
                 is_superuser_function,
                 autorun):
        self.function = function
        self.bind_prefix = bind_prefix
        self.alias = alias
        self.help_doc = help_doc
        self.need_self_process = need_self_process
        self.is_admin_function = is_admin_function
        self.is_base_function = is_base_function
        self.is_superuser_function = is_superuser_function
        self.autorun = autorun
