import asyncio
import uuid

import orjson
from fastapi import WebSocket

from bots.web.features import features as web_features
from core.builtins.filter import filter_badwords
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import PlainElement, ImageElement
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.logger import Logger


class WebContextManager(ContextManager):
    context: dict[str, dict] = {}
    features: Features = web_features
    typing_tasks: dict[str, asyncio.Task[None]] = {}
    TYPING_MAX_LIFETIME = 60

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        return True

    @classmethod
    def _get_websocket(cls, session_info: SessionInfo) -> WebSocket | None:
        """Return the socket which owns this session.

        A normal session must keep using the socket from which its message
        arrived.  Only fetched sessions (scheduled or otherwise proactive
        messages) may fall back to the most recently connected console.
        """
        if not getattr(session_info, "fetch", False):
            context = cls.context.get(session_info.session_id)
            if isinstance(context, dict):
                websocket = context.get("websocket")
                if websocket is not None:
                    return websocket
            return None
        return Temp.data.get("web_chat_websocket")

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        websocket = cls._get_websocket(session_info)
        sends = []

        if isinstance(message, MessageNodes):
            Logger.error("This session does not support message nodes, check if bug exists.")
            return []

        for x in message.as_sendable(session_info):
            if isinstance(x, PlainElement):
                x.text = session_info.locale.t_str(filter_badwords(x.text))
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
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
    ) -> list[str]:
        # 控制台不存在公开场景，私信与普通发送等价；但平台发送失败仍须
        # 遵守 ContextManager 契约，以空列表表示无法送达。
        try:
            return await cls.send_message(
                session_info,
                message,
                quote=False,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception(f"Failed to send private message to {user_id}: ")
            return []

    @classmethod
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        try:
            websocket = cls._get_websocket(session_info)

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
            websocket = cls._get_websocket(session_info)

            resp = {"action": "reaction", "id": message_id[-1], "emoji": emoji, "add": True}
            if websocket:
                await websocket.send_text(orjson.dumps(resp).decode())
            Logger.info(f'Added reaction "{emoji}" to message {message_id} in session {session_info.session_id}')
        except Exception:
            Logger.exception(
                f'Failed to add reaction "{emoji}" to message {message_id} in session {session_info.session_id}: '
            )

    @classmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        try:
            websocket = cls._get_websocket(session_info)

            resp = {"action": "reaction", "id": message_id[-1], "emoji": emoji, "add": False}
            if websocket:
                await websocket.send_text(orjson.dumps(resp).decode())
            Logger.info(f'Removed reaction "{emoji}" to message {message_id} in session {session_info.session_id}')
        except Exception:
            Logger.exception(
                f'Failed to remove reaction "{emoji}" to message {message_id} in session {session_info.session_id}: '
            )

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        previous = cls.typing_flags.pop(session_info.session_id, None)
        if previous:
            previous.set()
        previous_task = cls.typing_tasks.pop(session_info.session_id, None)
        if previous_task:
            previous_task.cancel()
            await asyncio.gather(previous_task, return_exceptions=True)
        flag = asyncio.Event()
        cls.typing_flags[session_info.session_id] = flag

        async def _typing():
            try:
                async with asyncio.timeout(cls.TYPING_MAX_LIFETIME):
                    ctx = cls.context.get(session_info.session_id)
                    if not ctx:
                        return
                    websocket = cls._get_websocket(session_info)
                    resp = {"action": "typing", "status": "start", "id": session_info.message_id}
                    if websocket:
                        await websocket.send_text(orjson.dumps(resp).decode())
                    await flag.wait()
            except TimeoutError:
                Logger.debug(f"Typing state expired in session: {session_info.session_id}")
                try:
                    websocket = cls._get_websocket(session_info)
                    if websocket:
                        resp = {"action": "typing", "status": "end", "id": session_info.message_id}
                        await websocket.send_text(orjson.dumps(resp).decode())
                except Exception:
                    Logger.exception()
            except Exception:
                Logger.exception()
            finally:
                if cls.typing_flags.get(session_info.session_id) is flag:
                    cls.typing_flags.pop(session_info.session_id, None)
                current_task = asyncio.current_task()
                if cls.typing_tasks.get(session_info.session_id) is current_task:
                    cls.typing_tasks.pop(session_info.session_id, None)

        cls.typing_tasks[session_info.session_id] = asyncio.create_task(
            _typing(), name=f"web-typing-{session_info.session_id}"
        )

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        flag = cls.typing_flags.pop(session_info.session_id, None)
        if flag:
            flag.set()
        task = cls.typing_tasks.pop(session_info.session_id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        # 这里可以添加结束输入状态的逻辑
        try:
            websocket = cls._get_websocket(session_info)

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
            websocket = cls._get_websocket(session_info)

            resp = {"action": "typing", "status": "error", "id": session_info.message_id}
            if websocket:
                await websocket.send_text(orjson.dumps(resp).decode())
        except Exception:
            Logger.exception()
