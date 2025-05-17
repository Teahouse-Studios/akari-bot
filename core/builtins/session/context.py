from typing import Any, Union, Optional, List

from core.builtins.message.chain import MessageChain
from core.builtins.session import SessionInfo
from core.builtins.session.features import Features


class ContextManager:
    context: dict[str, Any] = {}
    features: Optional[Features] = Features

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: Any):
        cls.context[session_info.session_id] = context

    @classmethod
    def del_context(cls, session_info: SessionInfo):
        if session_info.session_id in cls.context:
            del cls.context[session_info.session_id]

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: Union[MessageChain, str], quote: bool = True,) -> List[str]:
        """
        发送消息到指定的会话。
        :param session_info: 会话信息
        :param message: 消息内容，可以是 MessageChain 或字符串
        :param quote: 是否引用消息
        :return: 消息 ID 列表
        """
        if isinstance(message, str):
            message = MessageChain.assign(message)
        if not isinstance(message, MessageChain):
            raise TypeError("Message must be a MessageChain or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError        # 请继承 class 后实现方法

    class Typing:
        def __init__(self, session_info: SessionInfo):
            self.session_info = session_info

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
