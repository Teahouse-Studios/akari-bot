import asyncio
from typing import Any, Union, Optional, List

from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.builtins.session.features import Features
from core.logger import Logger


class ContextManager:
    context: dict[str, Any] = {}
    features: Optional[Features] = Features
    typing_flags: dict[str, asyncio.Event] = {}

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: Any):
        cls.context[session_info.session_id] = context

    @classmethod
    def del_context(cls, session_info: SessionInfo):
        if session_info.session_id in cls.context:
            del cls.context[session_info.session_id]

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        """
        检查会话权限。
        :param session_info: 会话信息
        :return: 是否有权限
        """
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
        raise NotImplementedError

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: MessageChain, quote: bool = True,) -> List[str]:
        """
        发送消息到指定的会话。
        :param session_info: 会话信息
        :param message: 消息内容，可以是 MessageChain 或字符串
        :param quote: 是否引用消息
        :return: 消息 ID 列表
        """

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError        # 请继承 class 后实现方法

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: list[str]) -> None:
        """
        删除指定会话中的消息。
        :param session_info: 会话信息
        :param message_id: 消息 ID 列表（为最大兼容，请将元素转换为str，若实现需要传入其他类型再在下方另行实现）
        """
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError        # 请继承 class 后实现方法

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        """
        开始输入状态
        :param session_info: 会话信息
        """
        async def _typing():
            if session_info.session_id not in cls.context:
                raise ValueError("Session not found in context")
            # 这里可以添加开始输入状态的逻辑
            Logger.debug(f"Start typing in session: {session_info.session_id}")
            flag = asyncio.Event()
            cls.typing_flags[session_info.session_id] = flag
            await flag.wait()
        asyncio.create_task(_typing())

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        """
        结束输入状态
        :param session_info: 会话信息
        """
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        if session_info.session_id in cls.typing_flags:
            cls.typing_flags[session_info.session_id].set()
            del cls.typing_flags[session_info.session_id]
        # 这里可以添加结束输入状态的逻辑
        Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        """
        发送错误信号
        :param session_info: 会话信息
        :param args: 错误信息
        """
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加错误处理逻辑
