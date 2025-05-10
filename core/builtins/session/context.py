from typing import Any, Union

from core.builtins.message.chain import MessageChain
from core.builtins.session import SessionInfo


class ContextManager:
    context: dict[str, Any] = {}

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: Any):
        cls.context[session_info.session_id] = context

    @classmethod
    def del_context(cls, session_info: SessionInfo):
        if session_info.session_id in cls.context:
            del cls.context[session_info.session_id]

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: Union[MessageChain, str], quote: bool = True,):
        if isinstance(message, str):
            message = MessageChain.assign(message)
        if not isinstance(message, MessageChain):
            raise TypeError("Message must be a MessageChain or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError        # 请继承 class 后实现方法
