import asyncio
from abc import ABC, abstractmethod
from typing import Any

from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.logger import Logger


class ContextManager(ABC):
    context: dict[str, Any] = {}
    features: Features | None = Features
    typing_flags: dict[str, asyncio.Event] = {}
    context_marks_hold: dict[str, int] = {}

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: Any):
        cls.context[session_info.session_id] = context

    @classmethod
    def del_context(cls, session_info: SessionInfo):
        if session_info.session_id in cls.context and session_info.session_id not in cls.context_marks_hold:
            del cls.context[session_info.session_id]
            Logger.trace(f"Context for session {session_info.session_id} deleted.")
        if session_info.session_id in cls.context_marks_hold:
            Logger.trace(f"Context for session {session_info.session_id} is held, skipping deletion.")

    @classmethod
    def hold_context(cls, session_info: SessionInfo):
        """
        Hold the context for a session.
        """
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        if session_info.session_id in cls.context_marks_hold:
            cls.context_marks_hold[session_info.session_id] += 1
        else:
            cls.context_marks_hold[session_info.session_id] = 1
            Logger.trace(f"Context for session {session_info.session_id} is now held.")

    @classmethod
    def release_context(cls, session_info: SessionInfo):
        """
        Release the held context for a session.
        """
        if session_info.session_id in cls.context_marks_hold:
            cls.context_marks_hold[session_info.session_id] -= 1
            if cls.context_marks_hold[session_info.session_id] == 0:
                del cls.context[session_info.session_id]
                del cls.context_marks_hold[session_info.session_id]
                Logger.trace(f"Context for session {session_info.session_id} is released.")

    @classmethod
    @abstractmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        """
        检查会话权限。

        :param session_info: 会话信息
        :return: 是否有权限
        """
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    @abstractmethod
    async def send_message(cls, session_info: SessionInfo,
                           message: MessageChain | MessageNodes,
                           quote: bool = True,
                           enable_parse_message: bool = True,
                           enable_split_image: bool = True,
                           ) -> list[str]:
        """
        发送消息到指定的会话。

        :param session_info: 会话信息
        :param message: 消息内容，可以是 MessageChain 或字符串
        :param quote: 是否引用消息
        :param enable_parse_message: 是否允许解析消息。（此参数作接口兼容用，仅QQ平台使用，默认为True）
        :param enable_split_image: 是否允许拆分图片发送。（此参数作接口兼容用，仅Telegram平台使用，默认为True）
        :return: 消息 ID 列表
        """

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    @abstractmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: str | list[str]) -> None:
        """
        删除指定会话中的消息，可能需要该会话的管理员权限。

        :param session_info: 会话信息
        :param message_id: 消息 ID 列表（为最大兼容，请将元素转换为str，若实现需要传入其他类型再在下方另行实现）
        """
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    @abstractmethod
    async def restrict_member(cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None) -> None:
        """
        禁言指定会话中的成员，可能需要该会话的管理员权限。

        :param session_info: 会话信息
        :param user_id: 用户 ID
        :param duration: 禁言时长
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    @abstractmethod
    async def unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        """
        解除禁言指定会话中的成员，可能需要该会话的管理员权限。

        :param session_info: 会话信息
        :param user_id: 用户 ID
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    @abstractmethod
    async def kick_member(cls, session_info: SessionInfo, user_id: str | list[str], ban: bool = False) -> None:
        """
        踢出指定会话中的成员，可能需要该会话的管理员权限。

        :param session_info: 会话信息
        :param user_id: 用户 ID
        :param ban: 是否封禁用户
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    @abstractmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        """
        为指定消息添加反应。

        :param session_info: 会话信息
        :param message_id: 消息 ID
        :param emoji: 反应内容（如表情符号）
        """
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加表情反应的逻辑
        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    @abstractmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        """
        为指定消息删除反应。

        :param session_info: 会话信息
        :param message_id: 消息 ID
        :param emoji: 反应内容（如表情符号）
        """
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加表情反应的逻辑
        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    @abstractmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        """
        开始输入状态。

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
    @abstractmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        """
        结束输入状态。

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
    @abstractmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        """
        发送错误信号。

        :param session_info: 会话信息
        """
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加错误处理逻辑
