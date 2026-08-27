"""Web 平台会话 Socket 绑定与私信失败语义测试。"""

import asyncio
import importlib
import os
import tempfile
from unittest.mock import AsyncMock, patch

import orjson
from fastapi import WebSocketDisconnect

from bots.web.config import WebConfig
from bots.web.context import WebContextManager, _serialize_element, resolve_media_url
from bots.web.features import features as web_features
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import ButtonElement, ButtonFrameElement, ButtonRows, VideoElement
from core.builtins.message.internal import ActionText, Embed, EmbedField, Markdown, Audio
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.utils.session import inject_features
from core.tester import Tester, func_case


class _RecordingWebSocket:
    def __init__(self, error: BaseException | None = None):
        self.error = error
        self.payloads: list[str] = []

    async def send_text(self, payload: str):
        if self.error is not None:
            raise self.error
        self.payloads.append(payload)


def _session(session_id: str, *, fetch: bool = False) -> SessionInfo:
    return SessionInfo(
        target_id="Web|Console|0",
        target_from="Web|Console",
        client_name="Web",
        session_id=session_id,
        message_id="incoming-message",
        fetch=fetch,
    )


async def _test_video_element_web_serialization() -> bool:
    session = _session("web-video-serialization")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_file:
        video_file.write(b"video fixture")
        video_path = video_file.name
    try:
        serialized = await _serialize_element(VideoElement.assign(video_path), session)
        if serialized is None or serialized["type"] != "video":
            return False
        token = serialized["content"].rsplit("/", 1)[-1]
        return serialized["content"].startswith("/api/media/") and resolve_media_url(token) == video_path
    finally:
        os.unlink(video_path)


async def _test_passive_reply_uses_source_websocket() -> bool:
    session = _session("web-source-session")
    source = _RecordingWebSocket()
    latest = _RecordingWebSocket()
    previous = Temp.data.get("web_chat_websocket")
    WebContextManager.context[session.session_id] = {"websocket": source}
    Temp.data["web_chat_websocket"] = latest
    try:
        message_ids = await WebContextManager.send_message(session, MessageChain.assign("source reply"))
        return (
            len(message_ids) == 1
            and len(source.payloads) == 1
            and not latest.payloads
            and orjson.loads(source.payloads[0])["message"][0]["content"] == "source reply"
        )
    finally:
        WebContextManager.context.pop(session.session_id, None)
        if previous is None:
            Temp.data.pop("web_chat_websocket", None)
        else:
            Temp.data["web_chat_websocket"] = previous


async def _test_proactive_message_uses_latest_websocket() -> bool:
    session = _session("web-fetched-session", fetch=True)
    latest = _RecordingWebSocket()
    previous = Temp.data.get("web_chat_websocket")
    Temp.data["web_chat_websocket"] = latest
    try:
        message_ids = await WebContextManager.send_message(session, MessageChain.assign("proactive"))
        return len(message_ids) == 1 and len(latest.payloads) == 1
    finally:
        if previous is None:
            Temp.data.pop("web_chat_websocket", None)
        else:
            Temp.data["web_chat_websocket"] = previous


async def _test_private_message_failure_returns_empty() -> bool:
    session = _session("web-private-failure")
    WebContextManager.context[session.session_id] = {"websocket": _RecordingWebSocket(RuntimeError("closed"))}
    try:
        return (
            await WebContextManager.send_private_msg(
                session,
                "Web|0",
                MessageChain.assign("private"),
            )
            == []
        )
    finally:
        WebContextManager.context.pop(session.session_id, None)


async def _test_private_message_cancellation_propagates() -> bool:
    session = _session("web-private-cancel")
    WebContextManager.context[session.session_id] = {
        "websocket": _RecordingWebSocket(asyncio.CancelledError()),
    }
    try:
        try:
            await WebContextManager.send_private_msg(
                session,
                "Web|0",
                MessageChain.assign("private"),
            )
        except asyncio.CancelledError:
            return True
        return False
    finally:
        WebContextManager.context.pop(session.session_id, None)


async def _test_websocket_entry_binds_source_context() -> bool:
    with patch.object(WebConfig, "enable", False, create=True):
        web_bot = importlib.import_module("bots.web.bot")

    class _IncomingWebSocket:
        def __init__(self):
            self.accepted = False
            self.received = False

        async def accept(self):
            self.accepted = True

        async def receive_text(self):
            if not self.received:
                self.received = True
                return orjson.dumps(
                    {
                        "action": "send",
                        "id": "incoming-message",
                        "message": [{"type": "text", "content": "hello"}],
                    }
                ).decode()
            raise WebSocketDisconnect(code=1000)

        async def close(self):
            return None

    websocket = _IncomingWebSocket()
    session = _session("web-entry-session")
    assign = AsyncMock(return_value=session)
    process_message = AsyncMock()
    previous = Temp.data.get("web_chat_websocket")
    try:
        with (
            patch.object(web_bot.SessionInfo, "assign", assign),
            patch.object(
                web_bot.Bot,
                "process_message",
                process_message,
            ),
        ):
            await web_bot.websocket_chat(websocket)
        if not websocket.accepted or process_message.await_count != 1:
            return False
        context = process_message.await_args.args[1]
        return context["websocket"] is websocket and context["message"]["action"] == "send"
    finally:
        if previous is None:
            Temp.data.pop("web_chat_websocket", None)
        else:
            Temp.data["web_chat_websocket"] = previous


async def _test_latest_disconnect_restores_previous_websocket() -> bool:
    with patch.object(WebConfig, "enable", False, create=True):
        web_bot = importlib.import_module("bots.web.bot")

    class _WaitingWebSocket:
        def __init__(self):
            self.accepted = asyncio.Event()
            self.disconnect = asyncio.Event()

        async def accept(self):
            self.accepted.set()

        async def receive_text(self):
            await self.disconnect.wait()
            raise WebSocketDisconnect(code=1000)

        async def close(self):
            return None

    first = _WaitingWebSocket()
    second = _WaitingWebSocket()
    previous = Temp.data.get("web_chat_websocket")
    first_task = asyncio.create_task(web_bot.websocket_chat(first))
    second_task = None
    try:
        await asyncio.wait_for(first.accepted.wait(), timeout=1)
        second_task = asyncio.create_task(web_bot.websocket_chat(second))
        await asyncio.wait_for(second.accepted.wait(), timeout=1)
        if Temp.data.get("web_chat_websocket") is not second:
            return False

        second.disconnect.set()
        await asyncio.wait_for(second_task, timeout=1)
        return Temp.data.get("web_chat_websocket") is first
    finally:
        first.disconnect.set()
        second.disconnect.set()
        tasks = [first_task]
        if second_task is not None:
            tasks.append(second_task)
        await asyncio.gather(*tasks, return_exceptions=True)
        if previous is None:
            Temp.data.pop("web_chat_websocket", None)
        else:
            Temp.data["web_chat_websocket"] = previous


async def _test_restart_cleans_client_before_exit() -> bool:
    web_api = importlib.import_module("bots.web.api.api")
    order = []

    async def sleep(_delay):
        order.append("delay")

    async def cleanup():
        order.append("cleanup")

    def exit_process(code: int):
        order.append(f"exit:{code}")

    with (
        patch.object(web_api.asyncio, "sleep", new=sleep),
        patch.object(web_api, "client_cleanup", new=cleanup),
        patch.object(web_api.os, "_exit", new=exit_process),
    ):
        await web_api.restart()
    return order == ["delay", "cleanup", "exit:233"]


async def _test_restart_schedule_is_singleton_and_retained() -> bool:
    web_api = importlib.import_module("bots.web.api.api")
    gate = asyncio.Event()
    calls = 0

    async def restart():
        nonlocal calls
        calls += 1
        await gate.wait()

    previous = web_api._restart_task
    web_api._restart_task = None
    try:
        with patch.object(web_api, "restart", new=restart):
            first = web_api.schedule_restart()
            second = web_api.schedule_restart()
            retained = web_api._restart_task is first
            gate.set()
            await first
            await asyncio.sleep(0)
        return first is second and retained and calls == 1 and web_api._restart_task is None
    finally:
        task = web_api._restart_task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        web_api._restart_task = previous


def _featured_session(session_id: str) -> SessionInfo:
    """带 Web 平台能力位的会话，供元素渲染测试使用。"""
    session = _session(session_id)
    inject_features(session, web_features)
    return session


async def _capture_send(session: SessionInfo, chain: MessageChain | MessageNodes) -> dict:
    """发送消息并返回首条 Socket 收到的 JSON 负载。"""
    source = _RecordingWebSocket()
    WebContextManager.context[session.session_id] = {"websocket": source}
    await WebContextManager.send_message(session, chain)
    return orjson.loads(source.payloads[0])


async def _test_markdown_element_sends_text_type() -> bool:
    session = _featured_session("web-markdown-session")
    try:
        payload = await _capture_send(session, MessageChain.assign(Markdown("**加粗**")))
        item = payload["message"][0]
        return item["type"] == "text" and item["content"] == "**加粗**"
    finally:
        WebContextManager.context.pop(session.session_id, None)


async def _test_audio_element_sends_audio_type() -> bool:
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(b"fake audio")
        session = _featured_session("web-audio-session")
        try:
            payload = await _capture_send(session, MessageChain.assign(Audio(path)))
            item = payload["message"][0]
            token = item["content"].rsplit("/", 1)[-1]
            return (
                item["type"] == "audio"
                and item["content"].startswith("/api/media/")
                and resolve_media_url(token) == path
            )
        finally:
            WebContextManager.context.pop(session.session_id, None)
    finally:
        os.remove(path)


async def _test_action_text_element_sends_action_text_type() -> bool:
    session = _featured_session("web-action-text-session")
    try:
        payload = await _capture_send(
            session, MessageChain.assign(ActionText("~wiki 沙盒", show="沙盒", reference=True))
        )
        item = payload["message"][0]
        return (
            item["type"] == "action_text"
            and item["content"] == "~wiki 沙盒"
            and item["show"] == "沙盒"
            and "reference" not in item
        )
    finally:
        WebContextManager.context.pop(session.session_id, None)


async def _test_button_frame_element_sends_button_frame_type() -> bool:
    session = _featured_session("web-button-session")
    frame = ButtonFrameElement.assign(
        [
            ButtonRows.assign([ButtonElement.assign("帮助", "~help")]),
            ButtonRows.assign([ButtonElement.assign("文档", "https://example.com")]),
        ]
    )
    try:
        payload = await _capture_send(session, MessageChain.assign(frame))
        item = payload["message"][0]
        return item["type"] == "button_frame" and item["content"] == [
            [{"show": "帮助", "value": "~help", "reply_id": None}],
            [{"show": "文档", "value": "https://example.com", "reply_id": None}],
        ]
    finally:
        WebContextManager.context.pop(session.session_id, None)


async def _test_embed_element_sends_embed_type() -> bool:
    session = _featured_session("web-embed-session")
    embed = Embed(
        title="标题",
        description="描述",
        color=0xFF0000,
        fields=[EmbedField("字段名", "字段值", inline=True)],
    )
    try:
        payload = await _capture_send(session, MessageChain.assign(embed))
        item = payload["message"][0]
        content = item["content"]
        return (
            item["type"] == "embed"
            and content["title"] == "标题"
            and content["description"] == "描述"
            and content["color"] == 0xFF0000
            and content["image"] is None
            and content["thumbnail"] is None
            and content["fields"] == [{"name": "字段名", "value": "字段值", "inline": True}]
        )
    finally:
        WebContextManager.context.pop(session.session_id, None)


async def _test_message_nodes_sends_nodes_type() -> bool:
    session = _featured_session("web-nodes-session")
    nodes = MessageNodes.assign(
        [
            MessageChain.assign("第一条"),
            MessageChain.assign("第二条"),
        ],
        name="转发组",
    )
    try:
        payload = await _capture_send(session, nodes)
        item = payload["message"][0]
        content = item["content"]
        return (
            item["type"] == "nodes"
            and content["name"] == "转发组"
            and len(content["nodes"]) == 2
            and content["nodes"][0][0]["type"] == "text"
            and content["nodes"][0][0]["content"] == "第一条"
            and content["nodes"][1][0]["content"] == "第二条"
        )
    finally:
        WebContextManager.context.pop(session.session_id, None)


@func_case
async def test_web_adapter(tester: Tester):
    await tester.test(_test_passive_reply_uses_source_websocket, "Web 被动回复使用入站来源 Socket")
    await tester.test(_test_proactive_message_uses_latest_websocket, "Web 主动推送使用当前 Socket")
    await tester.test(_test_private_message_failure_returns_empty, "Web 私信异常返回空消息 ID")
    await tester.test(_test_private_message_cancellation_propagates, "Web 私信取消继续传播")
    await tester.test(_test_websocket_entry_binds_source_context, "Web 入站会话绑定来源 Socket")
    await tester.test(_test_latest_disconnect_restores_previous_websocket, "Web 最新连接断开恢复旧连接")
    await tester.test(_test_restart_cleans_client_before_exit, "Web 重启前清理客户端")
    await tester.test(_test_restart_schedule_is_singleton_and_retained, "Web 重启任务单例持有")
    await tester.test(_test_markdown_element_sends_text_type, "Web Markdown 元素降级为 text 类型")
    await tester.test(_test_audio_element_sends_audio_type, "Web 语音元素发出 audio 类型")
    await tester.test(_test_action_text_element_sends_action_text_type, "Web 指令操作元素发出 action_text 类型")
    await tester.test(_test_button_frame_element_sends_button_frame_type, "Web 按钮区元素发出 button_frame 类型")
    await tester.test(_test_embed_element_sends_embed_type, "Web Embed 元素发出 embed 类型")
    await tester.test(_test_message_nodes_sends_nodes_type, "Web 消息节点发出 nodes 类型")
    await tester.test(_test_video_element_web_serialization, "Web Video 元素使用临时媒体 URL")
    return tester
