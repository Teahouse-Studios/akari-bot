from typing import Optional, List

import orjson as json
from fastapi import WebSocket

from bots.web.features import Features
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import PlainElement, ImageElement
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.logger import Logger
from core.utils.image import msgnode2image


class MsgIdGenerator:
    value = 0

    @classmethod
    def next(cls) -> str:
        cls.value += 1
        return str(cls.value)


class WebContextManager(ContextManager):
    context: dict[str, dict] = {}
    features: Optional[Features] = Features

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        return True

    @classmethod
    async def send_message(cls,
                           session_info: SessionInfo,
                           message: MessageChain | MessageNodes,
                           quote: bool = True,
                           enable_parse_message: bool = True,
                           enable_split_image: bool = True
                           ) -> List[str]:
        websocket: WebSocket = Temp.data.get("web_chat_websocket")
        sends = []

        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))

        for x in message.as_sendable(session_info):
            if isinstance(x, PlainElement):
                sends.append({"type": "text", "content": x.text})
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                img_b64 = await x.get_base64(mime=True)
                sends.append({"type": "image", "content": img_b64})
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {img_b64[:50]}...")

        msg_id = MsgIdGenerator.next()
        if websocket:
            resp = {"action": "send", "message": sends, "id": msg_id}
            await websocket.send_text(json.dumps(resp).decode())
            return [msg_id]
        return []

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

        try:
            websocket: WebSocket = Temp.data.get("web_chat_websocket")

            resp = {"action": "delete", "id": message_id}
            if websocket:
                await websocket.send_text(json.dumps(resp).decode())
        except Exception:
            Logger.exception()

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        pass

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        pass

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        pass
