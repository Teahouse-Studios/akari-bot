from enum import Enum
from typing import Coroutine, Any, Optional, Callable


class Target:
    def __init__(self,
        fromId,
        fromName,
        senderId,
        senderName,
        msgFrom
    ):
        self.fromId = fromId
        self.fromName = fromName
        self.senderId = senderId
        self.senderName = senderName
        self.msgFrom = msgFrom



class Module:
    def __init__(self,
                 function: Callable,
                 bind_prefix: str,
                 alias: [str, tuple],
                 help_doc: str,
                 need_self_process: bool,
                 is_admin_function: bool,
                 is_base_function: bool,
                 is_superuser_function: bool,
                 autorun: bool):
        self.function = function
        self.bind_prefix = bind_prefix
        self.alias = alias
        self.help_doc = help_doc
        self.need_self_process = need_self_process
        self.is_admin_function = is_admin_function
        self.is_base_function = is_base_function
        self.is_superuser_function = is_superuser_function
        self.autorun = autorun
