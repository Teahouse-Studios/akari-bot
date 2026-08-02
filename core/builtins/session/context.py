"""
会话上下文管理模块 - 管理消息会话的生命周期和通信接口。

该模块提供了 ContextManager 抽象基类，定义了会话上下文的管理接口
以及消息发送、权限检查等核心功能的抽象方法。各个通讯平台的具体实现
应继承此类并实现所有抽象方法。
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from copy import copy
from typing import Any

from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.logger import Logger


class ContextManager(ABC):
    """
    上下文管理器抽象基类。

    定义了会话上下文的管理接口、消息发送接口、权限管理接口等，
    用于与各种通讯平台的集成。

    属性说明:
        context: 存储会话上下文的字典，键为 session_id，值为上下文对象
        features: 会话支持的功能特性对象
        typing_flags: 输入状态标志的事件对象字典
        context_marks_hold: 记录上下文被保持的次数（支持嵌套保持）
    """

    # 会话上下文存储 - 键为 session_id，值为上下文对象（如对应平台框架下的消息实例）
    context: dict[str, Any] = {}

    # 会话功能特性 - 标记该管理器支持的功能
    features: Features = Features()

    # 输入状态标志 - 记录正在输入的会话
    typing_flags: dict[str, asyncio.Event] = {}

    # 上下文持有计数 - 用于支持嵌套的上下文持有/释放
    context_marks_hold: dict[str, int] = {}

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: Any):
        """
        为会话添加上下文。

        :param session_info: 会话信息对象
        :param context: 要存储的上下文对象（通常是对应平台框架下的消息实例）
        """
        # 以 session_id 为键存储上下文
        cls.context[session_info.session_id] = context

    @classmethod
    def del_context(cls, session_info: SessionInfo):
        """
        删除会话的上下文。

        只有当上下文未被标记为保持时才会删除。如果上下文被保持，则跳过删除。

        :param session_info: 会话信息对象
        """
        # 检查上下文是否存在且未被保持
        if session_info.session_id in cls.context and session_info.session_id not in cls.context_marks_hold:
            del cls.context[session_info.session_id]
            Logger.trace(f"Context for session {session_info.session_id} deleted.")
        # 如果上下文被保持，记录日志但不删除
        if session_info.session_id in cls.context_marks_hold:
            Logger.trace(f"Context for session {session_info.session_id} is held, skipping deletion.")

    @classmethod
    def hold_context(cls, session_info: SessionInfo):
        """
        保持会话的上下文。

        防止上下文被删除。支持嵌套保持，每次调用增加计数。

        :param session_info: 会话信息对象
        :raises ValueError: 如果会话上下文不存在
        """
        # 检查上下文是否存在
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        # 增加持有计数
        if session_info.session_id in cls.context_marks_hold:
            cls.context_marks_hold[session_info.session_id] += 1
        else:
            cls.context_marks_hold[session_info.session_id] = 1
            Logger.trace(f"Context for session {session_info.session_id} is now held.")

    @classmethod
    def release_context(cls, session_info: SessionInfo):
        """
        释放会话的上下文保持。

        保持持有计数。当计数达到 0 时，上下文会被立即删除。

        :param session_info: 会话信息对象
        """
        # 递减保持计数
        if session_info.session_id in cls.context_marks_hold:
            cls.context_marks_hold[session_info.session_id] -= 1
            # 当计数达到 0 时，删除上下文和计数记录
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
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        """
        向会话所在的场景发送消息。

        :param session_info: 会话信息
        :param message: 消息内容，可以是 MessageChain 或字符串
        :param quote: 是否引用消息
        :param enable_parse_message: 是否允许解析消息。（此参数作接口兼容用，仅 QQ 平台使用，默认为 True）
        :param enable_split_image: 是否允许拆分图片发送。（此参数作接口兼容用，仅 Telegram 平台使用，默认为 True）
        :return: 消息 ID 列表
        """

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        raise NotImplementedError  # 请继承 class 后实现方法

    @classmethod
    def derive_private_session(cls, session_info: SessionInfo, target_id: str, target_from: str) -> SessionInfo:
        """
        由当前会话派生出一份指向私聊场景的会话信息，供 :meth:`send_private_msg` 复用发送逻辑。

        派生出的会话不沿用原会话的 session_id 与 message_id：前者会使上下文查找命中原场景的
        消息实例，从而将私信回复至原场景；后者会使私信引用一条并不存在于私聊中的消息。

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
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        """
        向指定用户单独发送私聊消息。

        与 :meth:`send_message` 不同，消息不会发往 ``session_info`` 所指的场景，
        ``session_info`` 仅用于取用语言、平台能力等上下文。

        实现须捕获平台侧的发送异常并返回空列表，调用方以是否取得消息 ID 判定成败。

        :param session_info: 会话信息
        :param user_id: 目标用户 ID（带平台前缀，如 ``QQ|10000``）
        :param message: 消息内容
        :param enable_parse_message: 是否允许解析消息
        :param enable_split_image: 是否允许拆分图片发送
        :return: 消息 ID 列表，为空表示发送失败（如对方未添加机器人为好友、未开启私信等）
        """
        raise NotImplementedError  # 请继承 class 后实现方法

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

        raise NotImplementedError  # 请继承 class 后实现方法

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

        raise NotImplementedError  # 请继承 class 后实现方法

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

        raise NotImplementedError  # 请继承 class 后实现方法

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

        raise NotImplementedError  # 请继承 class 后实现方法

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

        raise NotImplementedError  # 请继承 class 后实现方法

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
