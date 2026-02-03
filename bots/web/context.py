import asyncio
import uuid

import orjson
from fastapi import WebSocket

from bots.web.features import Features
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import PlainElement, ImageElement
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.logger import Logger
from core.utils.image import msgnode2image


class WebContextManager(ContextManager):
    context: dict[str, dict] = {}
    features: Features | None = Features

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
                           ) -> list[str]:
        websocket: WebSocket = Temp.data.get("web_chat_websocket")
        sends = []

        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))

        for x in message.as_sendable(session_info, parse_message=enable_parse_message):
            if isinstance(x, PlainElement):
                sends.append({"type": "text", "content": x.text})
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                img_b64 = await x.get_base64(mime=True)
                sends.append({"type": "image", "content": img_b64})
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {img_b64[:50]}...")

        msg_id = str(uuid.uuid4())
        if websocket:
            resp = {"action": "send", "message": sends, "id": msg_id}
            await websocket.send_text(orjson.dumps(resp).decode())
            return [msg_id]
        return []

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None) -> None:
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
                await websocket.send_text(orjson.dumps(resp).decode())
            Logger.info(f"Deleted message {message_id} in session {session_info.session_id}")
        except Exception:
            Logger.exception(f"Failed to delete message {message_id} in session {session_info.session_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        try:
            websocket: WebSocket = Temp.data.get("web_chat_websocket")

            resp = {"action": "reaction", "id": message_id[-1], "emoji": emoji, "add": True}
            if websocket:
                await websocket.send_text(orjson.dumps(resp).decode())
            Logger.info(f"Added reaction \"{emoji}\" to message {message_id} in session {session_info.session_id}")
        except Exception:
            Logger.exception(f"Failed to add reaction \"{emoji}\" to message {
                message_id} in session {session_info.session_id}: ")

    @classmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        try:
            websocket: WebSocket = Temp.data.get("web_chat_websocket")

            resp = {"action": "reaction", "id": message_id[-1], "emoji": emoji, "add": False}
            if websocket:
                await websocket.send_text(orjson.dumps(resp).decode())
            Logger.info(f"Removed reaction \"{emoji}\" to message {message_id} in session {session_info.session_id}")
        except Exception:
            Logger.exception(f"Failed to remove reaction \"{emoji}\" to message {
                message_id} in session {session_info.session_id}: ")

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        async def _typing():
            if session_info.session_id not in cls.context:
                raise ValueError("Session not found in context")
            # 这里可以添加开始输入状态的逻辑
            ctx = cls.context[session_info.session_id]
            if ctx:
                try:
                    websocket: WebSocket = Temp.data.get("web_chat_websocket")

                    resp = {"action": "typing", "status": "start", "id": session_info.message_id}
                    if websocket:
                        await websocket.send_text(orjson.dumps(resp).decode())
                except Exception:
                    Logger.exception()

                flag = asyncio.Event()
                cls.typing_flags[session_info.session_id] = flag
                await flag.wait()

        asyncio.create_task(_typing())

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        if session_info.session_id in cls.typing_flags:
            cls.typing_flags[session_info.session_id].set()
            del cls.typing_flags[session_info.session_id]
        # 这里可以添加结束输入状态的逻辑
        try:
            websocket: WebSocket = Temp.data.get("web_chat_websocket")

            resp = {"action": "typing", "status": "end", "id": session_info.message_id}
            if websocket:
                await websocket.send_text(orjson.dumps(resp).decode())
        except Exception:
            Logger.exception()

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加错误处理逻辑
        try:
            websocket: WebSocket = Temp.data.get("web_chat_websocket")

            resp = {"action": "typing", "status": "error", "id": session_info.message_id}
            if websocket:
                await websocket.send_text(orjson.dumps(resp).decode())
        except Exception:
            Logger.exception()
