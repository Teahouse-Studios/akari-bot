from typing import Any, Union

from core.builtins import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement
from core.builtins.session import SessionInfo
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
    async def send_message(cls, session_info: SessionInfo, message: Union[MessageChain, str], quote: bool = True, ):
        if isinstance(message, str):
            message = MessageChain.assign(message)
        if not isinstance(message, MessageChain):
            raise TypeError("Message must be a MessageChain or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        for x in message.as_sendable(session_info, embed=False):
            if isinstance(x, PlainElement):
                print(x.text)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                image_path = await x.get()
                img = PILImage.open(image_path)
                img.show()
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {image_path}")


Bot.ContextManager = ConsoleContextManager
