import asyncio
import secrets
import time
import uuid

import orjson
from fastapi import WebSocket

from bots.web.features import features as web_features
from core.builtins.filter import filter_badwords
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import (
    ActionTextElement,
    ButtonFrameElement,
    EmbedElement,
    ImageElement,
    PlainElement,
    AudioElement,
    VideoElement,
)
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.logger import Logger

_MEDIA_URL_LIFETIME = 600
_media_urls: dict[str, tuple[str, float]] = {}


def register_media_url(path: str) -> str:
    now = time.monotonic()
    _media_urls.update({token: value for token, value in _media_urls.items() if value[1] > now})
    token = secrets.token_urlsafe(32)
    _media_urls[token] = (path, now + _MEDIA_URL_LIFETIME)
    return f"/api/media/{token}"


def resolve_media_url(token: str) -> str | None:
    media = _media_urls.get(token)
    if not media:
        return None
    if media[1] <= time.monotonic():
        _media_urls.pop(token, None)
        return None
    return media[0]


def _serialize_buttons(frame: ButtonFrameElement) -> list[list[dict]]:
    """把按钮区序列化为二维数组，供前端渲染按钮行。"""
    rows = []
    for row in frame.rows:
        buttons = []
        for button in row.buttons:
            payload = button.payload
            buttons.append(
                {
                    "show": button.show,
                    "value": payload.value,
                    "reply_id": payload.reply_id,
                }
            )
        if buttons:
            rows.append(buttons)
    return rows


async def _serialize_embed(embed: EmbedElement, session_info: SessionInfo) -> dict:
    """把 Embed 序列化为前端可直接渲染的富文本卡片数据。"""
    image = await embed.image.get_base64(mime=True) if embed.image else None
    thumbnail = await embed.thumbnail.get_base64(mime=True) if embed.thumbnail else None

    raw_fields = embed.fields
    if raw_fields is None:
        raw_fields = []
    elif not isinstance(raw_fields, list):
        raw_fields = [raw_fields]
    fields = [
        {
            "name": session_info.locale.t_str(field.name),
            "value": session_info.locale.t_str(field.value),
            "inline": field.inline,
        }
        for field in raw_fields
    ]

    return {
        "title": session_info.locale.t_str(embed.title) if embed.title else None,
        "description": session_info.locale.t_str(embed.description) if embed.description else None,
        "url": embed.url,
        "timestamp": embed.timestamp,
        "color": embed.color,
        "author": session_info.locale.t_str(embed.author) if embed.author else None,
        "footer": session_info.locale.t_str(embed.footer) if embed.footer else None,
        "image": image,
        "thumbnail": thumbnail,
        "fields": fields,
    }


async def _serialize_element(x, session_info: SessionInfo) -> dict | None:
    """把单个可发送元素序列化为前端消息字典（发送规则的唯一落点）。

    :return: 前端消息字典；无法识别的元素返回 None，由调用方跳过。
    """
    if isinstance(x, PlainElement):
        return {"type": "text", "content": session_info.locale.t_str(filter_badwords(x.text))}
    if isinstance(x, ImageElement):
        return {"type": "image", "content": await x.get_base64(mime=True)}
    if isinstance(x, AudioElement):
        return {"type": "audio", "content": register_media_url(x.path)}
    if isinstance(x, VideoElement):
        return {"type": "video", "content": register_media_url(x.path)}
    if isinstance(x, ActionTextElement):
        return {
            "type": "action_text",
            "content": x.text.text,
            "show": x.show.text if x.show else x.text.text,
        }
    if isinstance(x, ButtonFrameElement):
        return {"type": "button_frame", "content": _serialize_buttons(x)}
    if isinstance(x, EmbedElement):
        return {"type": "embed", "content": await _serialize_embed(x, session_info)}
    return None


async def _serialize_chain(chain: MessageChain, session_info: SessionInfo) -> list[dict]:
    """把消息链序列化为前端消息数组，并逐元素记录发送日志。"""
    sends = []
    for x in chain.as_sendable(session_info):
        item = await _serialize_element(x, session_info)
        if item is None:
            continue
        sends.append(item)
        kind = item["type"]
        if kind == "text":
            Logger.info(f"[Bot] -> [{session_info.target_id}]: {item['content']}")
        elif kind == "image":
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {item['content'][:50]}...")
        elif kind == "audio":
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Audio: {x.path}")
        elif kind == "video":
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Video: {x.path}")
        elif kind == "action_text":
            Logger.info(f"[Bot] -> [{session_info.target_id}]: ActionText: {item['content']}")
        elif kind == "button_frame":
            Logger.info(f"[Bot] -> [{session_info.target_id}]: ButtonFrame")
        elif kind == "embed":
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Embed: {x.title or ''}")
    return sends


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
        sends: list[dict] = []

        if isinstance(message, MessageNodes):
            nodes = [await _serialize_chain(chain, session_info) for chain in message.values]
            sends.append({"type": "nodes", "content": {"name": message.name, "nodes": nodes}})
            Logger.info(f"[Bot] -> [{session_info.target_id}]: MessageNodes: {message.name} ({len(nodes)} nodes)")
        else:
            sends = await _serialize_chain(message, session_info)

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
