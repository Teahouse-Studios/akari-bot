"""会话上下文管理模块 - 管理消息会话的生命周期和通信接口。"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from copy import copy
from typing import Any

from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.bot_state import BotState
from core.constants.exceptions import SessionContextUnavailable
from core.logger import Logger


class ContextManager(ABC):
    """上下文管理器抽象基类。"""

    context: dict[str, Any] = {}

    features: Features = Features()

    typing_flags: dict[str, asyncio.Event] = {}

    context_marks_hold: dict[str, int] = {}

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: Any):
        """
        为会话添加上下文。

        :param session_info: 会话信息对象
        :param context: 要存储的上下文对象（通常是对应平台框架下的消息实例）
        """
        cls.context[session_info.session_id] = context

    @classmethod
    def del_context(cls, session_info: SessionInfo):
        """删除会话的上下文。

        :param session_info: 会话信息对象
        """
        if session_info.session_id in cls.context and session_info.session_id not in cls.context_marks_hold:
            del cls.context[session_info.session_id]
            Logger.trace(f"Context for session {session_info.session_id} deleted.")
        if session_info.session_id in cls.context_marks_hold:
            Logger.trace(f"Context for session {session_info.session_id} is held, skipping deletion.")

    @classmethod
    def hold_context(cls, session_info: SessionInfo):
        """保持会话的上下文。

        :param session_info: 会话信息对象
        :raises SessionContextUnavailable: 如果会话上下文不存在
        """
        if session_info.session_id not in cls.context:
            raise SessionContextUnavailable("Session not found in context")

        if session_info.session_id in cls.context_marks_hold:
            cls.context_marks_hold[session_info.session_id] += 1
        else:
            cls.context_marks_hold[session_info.session_id] = 1
            Logger.trace(f"Context for session {session_info.session_id} is now held.")

    @classmethod
    def release_context(cls, session_info: SessionInfo):
        """释放会话的上下文保持。

        :param session_info: 会话信息对象
        """
        if session_info.session_id in cls.context_marks_hold:
            cls.context_marks_hold[session_info.session_id] -= 1
            if cls.context_marks_hold[session_info.session_id] == 0:
                # 平台关闭流程可能已先清空上下文字典；release 仍须移除 hold 计数，
                # 不能因重复清理抛 KeyError 而让后台任务以未取回异常结束。
                cls.context.pop(session_info.session_id, None)
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
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def check_bot_state(cls, session_info: SessionInfo) -> BotState:
        """Return the bot's membership and platform permission state in a context."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        """
        向会话所在的场景发送消息。

        :param session_info: 会话信息
        :param message: 消息内容，可以是 MessageChain 或字符串
        :param quote: 是否引用消息
        :return: 消息 ID 列表
        """

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError

    @classmethod
    def derive_private_session(cls, session_info: SessionInfo, target_id: str, target_from: str) -> SessionInfo:
        """由当前会话派生出一份指向私聊场景的会话信息，供 :meth:`send_private_msg` 复用发送逻辑。

        :param session_info: 当前会话信息
        :param target_id: 私聊场景 ID
        :param target_from: 私聊场景前缀
        :return: 指向私聊场景的会话信息副本
        """
        private_session = copy(session_info)
        private_session.session_id = str(uuid.uuid4())
        private_session.target_id = target_id
        private_session.target_from = target_from
        private_session.message_id = None
        private_session.reply_id = None
        return private_session

    @classmethod
    @abstractmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
    ) -> list[str]:
        """向指定用户单独发送私聊消息。

        :param session_info: 会话信息
        :param user_id: 目标用户 ID（带平台前缀，如 ``QQ|10000``）
        :param message: 消息内容
        :return: 消息 ID 列表，为空表示发送失败（如对方未添加机器人为好友、未开启私信等）
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
        """
        删除指定场景中的消息，可能需要该场景的管理员权限。

        :param session_info: 会话信息
        :param message_id: 消息 ID 列表（为最大兼容，请将元素转换为 str，若实现需要传入其他类型再在下方另行实现）
        :param reason: 原因（可选）
        """
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def restrict_member(
        cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None = None, reason: str | None = None
    ) -> None:
        """
        禁言指定场景中的成员，可能需要该场景的管理员权限。

        :param session_info: 会话信息
        :param user_id: 用户 ID
        :param duration: 禁言时长
        :param reason: 原因（可选）
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        """
        解除禁言指定场景中的成员，可能需要该场景的管理员权限。

        :param session_info: 会话信息
        :param user_id: 用户 ID
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def kick_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        """
        踢出指定场景中的成员，可能需要该场景的管理员权限。

        :param session_info: 会话信息
        :param user_id: 用户 ID
        :param reason: 原因（可选）
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def ban_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        """
        封禁指定场景中的成员，可能需要该场景的管理员权限。

        :param session_info: 会话信息
        :param user_id: 用户 ID
        :param reason: 原因（可选）
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def unban_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        """
        解除封禁指定场景中的成员，可能需要该场景的管理员权限。

        :param session_info: 会话信息
        :param user_id: 用户 ID
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def grant_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        """为场景成员授予平台原生权限组或角色。"""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def revoke_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        """移除场景成员的平台原生权限组或角色。"""
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
