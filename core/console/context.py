from typing import Any, Union

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.context import ContextManager
from core.logger import Logger
from .features import Features

from PIL import Image as PILImage


class ConsoleContextManager(ContextManager):
    context: dict[str, Any] = {}
    features = Features

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
        return True

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: Union[MessageChain, str], quote: bool = True, ):
        if isinstance(message, str):
            message = MessageChain.assign(message)
        if not isinstance(message, MessageChain):
            raise TypeError("Message must be a MessageChain or str")

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        for x in message.as_sendable(session_info):
            if isinstance(x, PlainElement):
                print(x.text)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                image_path = await x.get()
                img = PILImage.open(image_path)
                img.show()
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {image_path}")

        return ['0']

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

        print(
            f"(Tried to delete {str(message_id)}, but I\'m a console so I cannot do it :< )"
        )
