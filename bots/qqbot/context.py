import asyncio
import html
import time
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Union
from urllib.parse import quote

import botpy
from botpy.interaction import Interaction
from botpy.message import BaseMessage, C2CMessage, DirectMessage, GroupMessage, Message
from botpy.protocol import ApiError, MediaFileType, MediaSendResult, MessageType, ReplyTarget
from botpy.types.group import SetMemberMuteState
from botpy.types.message import Reference, KeyboardPayload
from botpy.types.inline import Keyboard, Button, KeyboardRow, RenderData, Action, Permission

from bots.qqbot.features import features as qqbot_features
from bots.qqbot.info import (
    client_name,
    sender_tiny_prefix,
    target_group_prefix,
    target_direct_prefix,
    target_guild_prefix,
    target_c2c_prefix,
)
from bots.qqbot.utils import url_filter
from core.builtins.filter import filter_badwords
from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import (
    ActionTextElement,
    ButtonFrameElement,
    ButtonRows,
    PlainElement,
    MarkdownElement,
    ImageElement,
    AudioElement,
    VideoElement,
    MentionElement,
    URLElement,
)
from core.builtins.message.internal import I18NContext, Image
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from bots.qqbot.config import QQBotConfig
from core.config.base import CoreConfig
from core.constants.path import assets_path
from core.logger import Logger
from core.utils.random import Random
from core.utils.table import escape_table_cell, resolve_table_columns

qq_typing_emoji = str(QQBotConfig.qq_typing_emoji)
qq_limited_emoji = str(QQBotConfig.qq_limited_emoji)
qq_use_markdown = QQBotConfig.qq_use_markdown

# 平台对指令操作标签内文本的字符数上限，按 urlencode 前的原文计算
ACTION_TEXT_MAX_LENGTH = 100
EXPIRED_REPLY_MESSAGE_CODE = 40034005
PERMISSION_CACHE_TTL = 3600
PERMISSION_CACHE_MAX_SIZE = 4096
INITIATIVE_QUEUE_MAX_SIZE = 128
HIGH_PRIORITY_BURST = 5
HIGH_PRIORITY_QUEUE_RESERVE = 16
ADAPTER_SHUTDOWN_TIMEOUT = 10
TYPING_EMOTE_DIR = assets_path / "emotes" / "typing"
TYPING_EMOTES = tuple(sorted(TYPING_EMOTE_DIR.glob("*.gif")))


def _load_s3_storage():
    from core.utils.s3 import S3Storage

    return S3Storage


def _truncate_action_text(value: str, field: str) -> str:
    """
    按平台上限截断指令操作的文本。

    截断后的 text 会使用户点击标签得到残缺命令，故记录截断前的长度以便排查。

    :param value: 原始文本。
    :param field: 字段名，仅用于日志。
    :return: 截断后的文本。
    """
    if len(value) <= ACTION_TEXT_MAX_LENGTH:
        return value
    Logger.warning(f"ActionText {field} exceeds {ACTION_TEXT_MAX_LENGTH} characters ({len(value)}), truncated.")
    return value[:ACTION_TEXT_MAX_LENGTH]


def _render_action_text(element: ActionTextElement) -> str:
    """
    将指令操作元素渲染为平台的参数指令标签。

    此处的 urlencode 与 KE 码中的 urlencode 互不相干：前者满足平台传值要求，
    后者规避 KE 码分隔符冲突。元素既可能经 KE 码路径抵达，也可能直接放入消息链，
    故两处各自编码。

    :param element: 内层文案已解析的指令操作元素。
    :return: 标签字符串；text 为空时返回空字符串。
    """
    text = element.text.text if element.text else ""
    if not text:
        return ""
    attrs = [f'text="{quote(_truncate_action_text(text, "text"), safe="")}"']
    show = element.show.text if element.show else ""
    if show:
        attrs.append(f'show="{quote(_truncate_action_text(show, "show"), safe="")}"')
    attrs.append(f'reference="{"true" if element.reference else "false"}"')
    return f"<qqbot-cmd-input {' '.join(attrs)} />"


def _build_qqbot_keyboard(
    rows: list[ButtonRows], session_info: SessionInfo, target: ReplyTarget
) -> KeyboardPayload | None:
    """将 ButtonFrame 的按钮行转换为 QQBot 键盘。"""
    if not rows:
        return None
    keyboard_rows = []
    button_id = 0
    for row in rows:
        buttons = []
        for message_button in row.buttons:
            payload = message_button.payload
            button_id += 1
            buttons.append(
                Button(
                    id=str(button_id),
                    render_data=RenderData(
                        label=message_button.show,
                        visited_label=session_info.locale.t("message.selected") + message_button.show,
                        style=0,
                    ),
                    action=Action(
                        type=0 if payload.value.startswith(("http://", "https://")) else 1,
                        permission=Permission(
                            type=2 if target.scope == "c2c" else 0,
                            specify_user_ids=[session_info.get_common_sender_id()],
                            specify_role_ids=["1"],
                        ),
                        click_limit=1,
                        data=payload.to_data(),
                        at_bot_show_channel_list=False,
                    ),
                )
            )
        if buttons:
            keyboard_rows.append(KeyboardRow(buttons=buttons))
    if not keyboard_rows:
        return None
    return KeyboardPayload(content=Keyboard(rows=keyboard_rows))


# 节点表格的高度上限，按「编号行 + 内容行」计对。过宽的表格平台会渲染失败，故此值宜小不宜大：
# 每多一对，列数减半、单行长度随之减半。帮助的表格另有自己的上限，两者不共用。
MESSAGE_NODES_MAX_ROWS = 2
MARKDOWN_IMAGE_MAX_WIDTH = 128


def _markdown_image_size(image: ImageElement, width: int, height: int) -> tuple[int, int]:
    """计算 QQBot Markdown 图片尺寸；max_h 按兼容命名表示调用方指定的最大宽度。"""
    max_width = image.max_h or MARKDOWN_IMAGE_MAX_WIDTH
    scale = max_width / width if width > max_width else 1
    return int(width * scale), int(height * scale)


def nodes_to_table(session_info: SessionInfo, nodes: MessageNodes) -> str:
    """
    把消息节点摊平为一张 markdown 表。


    :param session_info: 会话信息，用于把各节点的消息链转为可发送形态。
    :param nodes: 消息节点。
    :return: 整张表格的 markdown 文本；无节点时返回节点组名称。
    """
    cells = []
    for node in nodes.values:
        pieces = [x.text for x in node.as_sendable(session_info, disable_markdown=True) if isinstance(x, PlainElement)]
        cells.append(escape_table_cell("\n".join(pieces)))
    if not cells:
        return escape_table_cell(nodes.name)

    columns = resolve_table_columns([len(cells)], minimum=1, max_rows=MESSAGE_NODES_MAX_ROWS)
    lines = [
        f"| {escape_table_cell(nodes.name)} |" + " |" * (columns - 1),
        "|" + "---|" * columns,
    ]
    for start in range(0, len(cells), columns):
        chunk = cells[start : start + columns]
        # 末对补空单元格，markdown 要求各行的列数一致
        padding = [""] * (columns - len(chunk))
        lines.append("| " + " | ".join([str(start + offset + 1) for offset in range(len(chunk))] + padding) + " |")
        lines.append("| " + " | ".join(chunk + padding) + " |")
    return "\n".join(lines)


# 用户权限缓存，用于部分场景接口未返回群聊内身份使用。只缓存管理员，缺失时安全退化为无权限。
permission_cache: OrderedDict[str, float] = OrderedDict()


def cache_permission(key: str, is_admin: bool, now: float | None = None) -> None:
    if not is_admin:
        permission_cache.pop(key, None)
        return
    permission_cache.pop(key, None)
    permission_cache[key] = time.monotonic() if now is None else now
    while len(permission_cache) > PERMISSION_CACHE_MAX_SIZE:
        permission_cache.popitem(last=False)


def get_cached_permission(key: str, now: float | None = None) -> bool:
    cached_at = permission_cache.get(key)
    if cached_at is None:
        return False
    now = time.monotonic() if now is None else now
    if now - cached_at > PERMISSION_CACHE_TTL:
        permission_cache.pop(key, None)
        return False
    permission_cache.move_to_end(key)
    return True


def _get_client():
    if QQBotContextManager.client is None:
        raise RuntimeError("QQBot client is not initialized")
    return QQBotContextManager.client


def _reply_target(session_info: SessionInfo, context: BaseMessage | Interaction | None = None) -> ReplyTarget:
    scope = {
        target_c2c_prefix: "c2c",
        target_group_prefix: "group",
        target_guild_prefix: "channel",
        target_direct_prefix: "dm",
    }.get(session_info.target_from)
    if scope is None:
        raise ValueError(f"Unsupported QQBot target: {session_info.target_from}")
    message_id = session_info.message_id if context is not None and not isinstance(context, Interaction) else None
    return ReplyTarget(scope=scope, target_id=session_info.get_common_target_id(), message_id=message_id)


def _message_ids(result) -> list[str]:
    if isinstance(result, MediaSendResult):
        return _message_ids(result.message)
    if isinstance(result, list):
        return [message_id for item in result for message_id in _message_ids(item)]
    if isinstance(result, Mapping) and result.get("id"):
        return [str(result["id"])]
    return []


def _is_expired_reply_message_error(error: ApiError) -> bool:
    """判断 QQ OpenAPI 异常是否表示被回复的消息 ID 已过期。"""
    codes = [error.code]
    if isinstance(error.response, Mapping):
        codes.extend((error.response.get("code"), error.response.get("err_code")))
    return any(str(code) == str(EXPIRED_REPLY_MESSAGE_CODE) for code in codes if code is not None)


class _TypingState:
    """一轮输入状态的生命周期标志。

    ``sending`` 表示普通回复已完成资源准备并进入发送阶段，用于阻止 typing 消息
    后发；``spoken`` 只记录平台已经成功接受至少一条普通消息。
    """

    __slots__ = ("finished", "sending", "spoken")

    def __init__(self):
        self.finished = asyncio.Event()
        self.sending = asyncio.Event()
        self.spoken = asyncio.Event()


class _PreparedMessage:
    """已完成资源准备、只差调用平台消息发送接口的消息。"""

    __slots__ = ("has_payload", "queue_key", "send")

    def __init__(
        self,
        target: ReplyTarget,
        send: Callable[[], Awaitable[list[str]]],
        *,
        has_payload: bool,
    ):
        self.queue_key = f"{target.scope}|{target.target_id}"
        self.send = send
        self.has_payload = has_payload


class _QueuedMessage:
    """等待进入 QQ OpenAPI 消息发送阶段的任务。"""

    __slots__ = ("future", "prepared", "sequence", "started", "typing_prompt", "typing_state")

    def __init__(
        self,
        future: asyncio.Future[list[str]],
        prepared: _PreparedMessage,
        sequence: int,
        *,
        typing_prompt: bool,
        typing_state: _TypingState | None,
    ):
        self.future = future
        self.prepared = prepared
        self.sequence = sequence
        self.started = False
        self.typing_prompt = typing_prompt
        self.typing_state = typing_state


class _MessageSendQueue:
    """同一 QQ 目标的短生命周期发送整形队列。"""

    __slots__ = ("pending", "worker")

    def __init__(self):
        self.pending: list[_QueuedMessage] = []
        self.worker: asyncio.Task[None] | None = None


class QQBotContextManager(ContextManager):
    context: dict[str, Union[BaseMessage, Interaction]] = {}
    features: Features = qqbot_features
    typing_states: dict[str, _TypingState] = {}
    typing_tasks: dict[str, asyncio.Task[None]] = {}
    message_send_queues: dict[str, _MessageSendQueue] = {}
    message_send_sequence = 0
    client: botpy.Client | None = None
    _shutting_down = False

    # 机器人沉默满此秒数后，才在群聊中补发输入提示
    TYPING_PROMPT_DELAY = 5
    # 输入提示的最长存活时间，用于在结束信号丢失时强制撤回。
    TYPING_PROMPT_MAX_LIFETIME = 60

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: BaseMessage):
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
    def prepare_start(cls) -> None:
        """允许新一轮客户端生命周期继续创建适配器任务。"""
        cls._shutting_down = False

    @classmethod
    async def shutdown(cls) -> None:
        """停止适配器自有任务，并释放所有等待发送结果的调用方。"""
        cls._shutting_down = True

        # 不直接取消 Typing 任务：平台可能已经接受提示消息，但 SDK 尚未返回其消息 ID。
        # 先发结束信号并等待正常收尾，使任务有机会在 finally 中撤回提示。
        for state in list(cls.typing_states.values()):
            state.finished.set()
        typing_tasks = list(dict.fromkeys(cls.typing_tasks.values()))
        if typing_tasks:
            typing_group = asyncio.gather(*typing_tasks, return_exceptions=True)
            try:
                await asyncio.wait_for(asyncio.shield(typing_group), timeout=ADAPTER_SHUTDOWN_TIMEOUT)
            except TimeoutError:
                Logger.warning("QQBot typing tasks did not stop in time; cancelling the remaining tasks.")
                for task in typing_tasks:
                    if not task.done():
                        task.cancel()
                await typing_group
        cls.typing_states.clear()
        cls.typing_tasks.clear()

        # Typing 已尽量完成撤回后，再停止实际发送队列。worker 的取消分支会把当前
        # 与尚未开始的 Future 解析为 []，维持 ContextManager 的发送失败约定。
        queues = list(dict.fromkeys(cls.message_send_queues.values()))
        workers = [queue.worker for queue in queues if queue.worker is not None]
        for worker in workers:
            if not worker.done():
                worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        for queue in queues:
            for queued in queue.pending:
                if not queued.future.done():
                    queued.future.set_result([])
            queue.pending.clear()
        cls.message_send_queues.clear()

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        ctx: BaseMessage | None = cls.context.get(session_info.session_id)

        if ctx:
            if isinstance(ctx, Message):
                info = ctx.member
                admins = ["2", "4"]
                for x in admins:
                    if x in info.roles:
                        return True
            elif isinstance(ctx, DirectMessage):
                return True
            elif isinstance(ctx, GroupMessage):
                if ctx.author.member_role in ["admin", "owner"]:
                    return True
                return False
            elif isinstance(ctx, C2CMessage):
                return True
            else:
                return get_cached_permission(f"{session_info.target_id}|{session_info.sender_id}")
        return False

    @classmethod
    async def _prepare_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        _ignore_retries: bool = False,
        _typing_prompt: bool = False,
        _force_plain: bool = False,
    ) -> _PreparedMessage:
        """完成消息渲染和媒体上传，不调用最终的消息发送接口。"""
        ctx: BaseMessage | Interaction | None = cls.context.get(session_info.session_id)
        client = _get_client()
        target = _reply_target(session_info, ctx)

        if isinstance(message, MessageNodes):
            message = MessageChain.assign(
                MarkdownElement.assign(nodes_to_table(session_info, message), disable_joke=True)
            )

        async def empty_send() -> list[str]:
            return []

        async def prepare_separate_media(elements: list[AudioElement | VideoElement]):
            media = []
            for element in elements:
                media_type = MediaFileType.VOICE if isinstance(element, AudioElement) else MediaFileType.VIDEO
                if target.scope in ("group", "c2c"):
                    upload = await client.upload_media(target, media_type, local_path=element.path)
                    file_info = upload.get("file_info") if isinstance(upload, Mapping) else None
                    if not file_info:
                        raise RuntimeError("QQBot media upload response does not contain file_info")
                    media.append((element, {"file_info": file_info}))
                else:
                    media.append((element, element.path))
            return media

        async def send_separate_media(prepared_media) -> list[str]:
            msg_ids = []
            for element, media in prepared_media:
                media_name = "audio" if isinstance(element, AudioElement) else "video"
                try:
                    if target.scope in ("group", "c2c"):
                        result = await client.send(target, msg_type=MessageType.MEDIA, media=media)
                    else:
                        result = await client.send(target, extra={f"file_{media_name}": media})
                    msg_ids.extend(_message_ids(result))
                    cls._on_message_sent(session_info)
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {media_name.title()}: {str(element)}")
                except Exception:
                    if not msg_ids:
                        raise
                    Logger.exception(
                        f"QQBot {media_name} message to {session_info.target_id} was only partially sent; "
                        f"returning the recorded message IDs {msg_ids}: "
                    )
                    break
            return msg_ids

        async def prepare_plain_message() -> _PreparedMessage:
            plains: list[PlainElement] = []
            images: list[ImageElement] = []
            media: list[AudioElement | VideoElement] = []

            for x in message.as_sendable(session_info, disable_markdown=True):
                if isinstance(x, PlainElement):
                    x.text = session_info.locale.t_str(filter_badwords(html.unescape(x.text)))
                    if x.allow_parse:
                        x.text = match_atcode(x.text, client_name, "<@{uid}>")
                    plains.append(x)
                elif isinstance(x, ImageElement):
                    images.append(x)
                elif isinstance(x, (AudioElement, VideoElement)):
                    media.append(x)
                elif isinstance(x, MentionElement):
                    if x.client == client_name and session_info.target_from in (
                        target_guild_prefix,
                        target_group_prefix,
                    ):
                        plains.append(PlainElement(text=f"<@{x.id}>"))
            if not plains and not images and not media:
                return _PreparedMessage(target, empty_send, has_payload=False)

            msg = "\n".join(x.text for x in plains).strip()
            if session_info.target_from in (target_guild_prefix, target_direct_prefix):
                msg = url_filter(msg)

            message_reference = None
            if quote and not images:
                if isinstance(ctx, (Message, DirectMessage)):
                    message_reference = Reference(message_id=ctx.id, ignore_get_message_error=False)
                elif isinstance(ctx, GroupMessage) and ctx.message_scene:
                    ext = ctx.message_scene.get("ext") or []
                    if ext and ext[0].startswith("msg_idx=REFIDX"):
                        message_reference = Reference(
                            message_id=ext[0].replace("msg_idx=", ""),
                            ignore_get_message_error=False,
                        )

            if quote and images and isinstance(ctx, Message):
                msg = f"<@{ctx.author.id}> \n{msg}"

            prepared_images: list[tuple[ImageElement, str | Mapping]] = []
            for image in images:
                image_path = await image.get()
                if target.scope in ("group", "c2c"):
                    upload = await client.upload_media(target, MediaFileType.IMAGE, local_path=image_path)
                    file_info = upload.get("file_info") if isinstance(upload, Mapping) else None
                    if not file_info:
                        raise RuntimeError("QQBot media upload response does not contain file_info")
                    prepared_images.append((image, {"file_info": file_info}))
                else:
                    prepared_images.append((image, image_path))

            prepared_media = await prepare_separate_media(media)

            async def send_plain_message() -> list[str]:
                msg_ids = []
                if not plains and not images:
                    return await send_separate_media(media)
                send_target = target

                async def send_with_proactive_fallback(sender, /, *args, **kwargs):
                    """回复消息 ID 过期时，移除回复信息并立即改发一条主动消息。"""
                    nonlocal send_target
                    try:
                        return await sender(send_target, *args, **kwargs)
                    except ApiError as error:
                        if send_target.message_id is None or not _is_expired_reply_message_error(error):
                            raise

                        Logger.warning(
                            f"Reply message {send_target.message_id} expired when sending to "
                            f"{send_target.scope}|{send_target.target_id}; retrying as a proactive message."
                        )
                        send_target = ReplyTarget(scope=send_target.scope, target_id=send_target.target_id)
                        return await sender(send_target, *args, **kwargs)

                async def record(result, image: ImageElement | None = None):
                    msg_ids.extend(_message_ids(result))
                    if not _typing_prompt:
                        cls._on_message_sent(session_info)
                    if image:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image)}")

                try:
                    remaining_images = list(prepared_images)
                    if remaining_images:
                        image, prepared_image = remaining_images.pop(0)
                        if send_target.scope in ("group", "c2c"):
                            result = await send_with_proactive_fallback(
                                client.send,
                                content=msg or None,
                                msg_type=MessageType.MEDIA,
                                media=prepared_image,
                            )
                        else:
                            result = await send_with_proactive_fallback(
                                client.send,
                                content=msg or None,
                                message_reference=message_reference,
                                extra={"file_image": prepared_image},
                            )
                        await record(result, image)
                    else:
                        result = await send_with_proactive_fallback(
                            client.send, content=msg, message_reference=message_reference
                        )
                        await record(result)

                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                    for image, prepared_image in remaining_images:
                        if send_target.scope in ("group", "c2c"):
                            result = await send_with_proactive_fallback(
                                client.send,
                                msg_type=MessageType.MEDIA,
                                media=prepared_image,
                            )
                        else:
                            result = await send_with_proactive_fallback(
                                client.send, extra={"file_image": prepared_image}
                            )
                        await record(result, image)
                except Exception:
                    if not msg_ids:
                        raise
                    Logger.exception(
                        f"QQBot message to {session_info.target_id} was only partially sent; "
                        f"returning the recorded message IDs {msg_ids}: "
                    )
                msg_ids.extend(await send_separate_media(prepared_media))
                return msg_ids

            return _PreparedMessage(target, send_plain_message, has_payload=bool(plains or images or media))

        async def prepare_markdown_message() -> _PreparedMessage:
            texts = []
            media: list[AudioElement | VideoElement] = []

            if quote and ctx and session_info.target_from in (target_guild_prefix, target_group_prefix):
                texts.append(f'<qqbot-at-user id="{session_info.get_common_sender_id()}" />')
            converted_message = message.as_sendable(session_info)
            possibly_choices = [row for x in converted_message if isinstance(x, ButtonFrameElement) for row in x.rows]
            keyboard = _build_qqbot_keyboard(possibly_choices, session_info, target)

            _use_markdown = True

            if converted_message.only(PlainElement) and not converted_message.contains(MarkdownElement):
                _use_markdown = False
            if converted_message.only(ImageElement) and len(converted_message) == 1:
                _use_markdown = False
            if message.contains(URLElement):
                for x in message.values:
                    if isinstance(x, URLElement):
                        if not x.trusted:
                            _use_markdown = True

            if keyboard:
                _use_markdown = True
            if not _use_markdown:
                Logger.debug("MessageElements do not require markdown, sending as plain message instead of markdown.")
                return await prepare_plain_message()

            # 指令操作是行内元素：它自身与紧随其后的文本都须并入上一项，
            # 否则 "\n".join(texts) 会将同一句话的末尾文本移至下一行。
            inline_pending = False
            s3_storage = None
            if any(isinstance(element, ImageElement) for element in converted_message):
                s3_storage = await asyncio.to_thread(_load_s3_storage)

            for x in converted_message:
                if isinstance(x, PlainElement):
                    x.text = session_info.locale.t_str(filter_badwords(html.unescape(x.text)))
                    if x.allow_parse:
                        x.text = match_atcode(x.text, client_name, "<@{uid}>")
                    if inline_pending and texts:
                        texts[-1] += x.text
                    else:
                        texts.append(x.text)
                    inline_pending = False
                elif isinstance(x, ImageElement):
                    if s3_storage is not None:
                        try:
                            upload = await s3_storage.upload_temp(await x.get())
                            if upload and "public_url" in upload:
                                w, h = await x.get_wh()
                                fin_w, fin_h = _markdown_image_size(x, w, h)
                                texts.append(f"![text #{fin_w}px #{fin_h}px]({upload['public_url']})")
                        except Exception:
                            Logger.exception(
                                f"Failed to upload a QQBot markdown image to S3 for {session_info.session_id}; "
                                "the remaining message will still be sent: "
                            )
                    inline_pending = False
                elif isinstance(x, (AudioElement, VideoElement)):
                    media.append(x)
                    inline_pending = False
                elif isinstance(x, MentionElement):
                    if x.client == client_name and session_info.target_from in (
                        target_guild_prefix,
                        target_group_prefix,
                    ):
                        texts.append(f'<qqbot-at-user id="{x.id}" />')
                    inline_pending = False
                elif isinstance(x, ActionTextElement):
                    tag = _render_action_text(x)
                    if tag:
                        if texts:
                            texts[-1] += tag
                        else:
                            texts.append(tag)
                    inline_pending = True
            if keyboard and not texts:
                texts.append("\u200b")
            prepared_media = await prepare_separate_media(media)
            if not texts and not prepared_media:
                return _PreparedMessage(target, empty_send, has_payload=False)

            msg = "\n".join(texts)

            async def send_markdown_message() -> list[str]:
                msg_ids = []
                if texts:
                    send_target = target
                    try:
                        result = await client.send_markdown(send_target, msg, keyboard=keyboard)
                    except ApiError as error:
                        if send_target.message_id is None or not _is_expired_reply_message_error(error):
                            raise
                        Logger.warning(
                            f"Reply message {send_target.message_id} expired when sending to "
                            f"{send_target.scope}|{send_target.target_id}; retrying as a proactive message."
                        )
                        send_target = ReplyTarget(scope=send_target.scope, target_id=target.target_id)
                        result = await client.send_markdown(send_target, msg, keyboard=keyboard)
                    msg_ids.extend(_message_ids(result))
                    if not _typing_prompt:
                        cls._on_message_sent(session_info)
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                msg_ids.extend(await send_separate_media(prepared_media))
                return msg_ids

            return _PreparedMessage(target, send_markdown_message, has_payload=bool(texts or prepared_media))

        # 会话的 support_markdown 由 resolve_features() 按用户偏好置定，用户关闭 markdown 后
        # 走纯文本路径；全局配置关闭时同样如此。
        if _force_plain or not qq_use_markdown or not session_info.support_markdown:
            return await prepare_plain_message()
        return await prepare_markdown_message()

    @classmethod
    async def _process_message_send_queue(cls, queue_key: str, queue: _MessageSendQueue) -> None:
        """按目标串行发送，并在每次平台调用前淘汰已经过时的 typing 提示。"""
        try:
            await asyncio.sleep(0)
            while queue.pending:
                queued = min(queue.pending, key=lambda item: item.sequence)
                queue.pending.remove(queued)
                queued.started = True
                if queued.future.cancelled():
                    continue

                # typing 出队后再让出一次执行权，允许同一时刻准备完成的普通回复
                # 先置位 sending；随后仍会在真正调用平台消息接口前作最后检查。
                await asyncio.sleep(0)
                state = queued.typing_state
                try:
                    if queued.typing_prompt and (state is None or state.finished.is_set() or state.sending.is_set()):
                        result = []
                    else:
                        result = await queued.prepared.send()
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    if not queued.future.done():
                        queued.future.set_exception(error)
                else:
                    if not queued.future.done():
                        queued.future.set_result(result)
        except asyncio.CancelledError:
            if "queued" in locals() and not queued.future.done():
                if cls._shutting_down:
                    queued.future.set_result([])
                else:
                    queued.future.cancel()
            raise
        finally:
            if cls.message_send_queues.get(queue_key) is queue:
                cls.message_send_queues.pop(queue_key, None)
            for pending in queue.pending:
                if not pending.future.done():
                    if cls._shutting_down:
                        pending.future.set_result([])
                    else:
                        pending.future.set_exception(RuntimeError("QQBot message send queue stopped unexpectedly"))

    @classmethod
    async def _send_prepared_message(
        cls,
        session_info: SessionInfo,
        prepared: _PreparedMessage,
        *,
        _typing_prompt: bool = False,
        _typing_state: _TypingState | None = None,
    ) -> list[str]:
        """进入实际消息发送阶段；调用前不再做媒体上传或图片读取。"""
        if cls._shutting_down or not prepared.has_payload:
            return []

        state = _typing_state or cls.typing_states.get(session_info.session_id)
        if _typing_prompt:
            if state is None or state.finished.is_set() or state.sending.is_set():
                return []
        elif state:
            cls._on_message_sending(session_info)

        queue = cls.message_send_queues.setdefault(prepared.queue_key, _MessageSendQueue())
        cls.message_send_sequence += 1
        future = asyncio.get_running_loop().create_future()
        queued = _QueuedMessage(
            future,
            prepared,
            cls.message_send_sequence,
            typing_prompt=_typing_prompt,
            typing_state=state,
        )
        queue.pending.append(queued)
        if queue.worker is None or queue.worker.done():
            queue.worker = asyncio.create_task(
                cls._process_message_send_queue(prepared.queue_key, queue),
                name=f"qqbot-message-send-{prepared.queue_key}",
            )

        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            if not queued.started:
                try:
                    queue.pending.remove(queued)
                except ValueError:
                    pass
                future.cancel()
            elif not future.done():
                future.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            raise

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        _ignore_retries: bool = False,
        _typing_prompt: bool = False,
        _force_plain: bool = False,
    ) -> list[str]:
        """保持原有公开行为：准备资源并等待实际发送完成后返回消息 ID。"""
        prepared = await cls._prepare_message(
            session_info,
            message,
            quote=quote,
            _ignore_retries=_ignore_retries,
            _typing_prompt=_typing_prompt,
            _force_plain=_force_plain,
        )
        return await cls._send_prepared_message(
            session_info,
            prepared,
            _typing_prompt=_typing_prompt,
        )

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
    ) -> list[str]:
        uid = user_id.split("|")[-1]

        try:
            # 客户端解析也可能在初始化失败或关闭期间抛错，仍应遵守私信失败返回空 ID 的契约。
            client = _get_client()
            if session_info.target_from == target_direct_prefix and user_id == session_info.sender_id:
                # 当前已处于私信场景中，无需另行创建
                target_id, target_from = session_info.target_id, target_direct_prefix
            elif user_id.startswith(sender_tiny_prefix):
                # 频道用户的私信须先以来源频道创建私信场景，取得专用的 guild_id 后方可发送
                target_parts = session_info.target_id.split("|")
                if session_info.target_from != target_guild_prefix or len(target_parts) < 3:
                    Logger.warning(
                        f"Cannot safely create a QQBot direct-message target for {user_id} "
                        f"from {session_info.target_id}; skipped private delivery."
                    )
                    return []
                guild_id = target_parts[2]
                dms = await client.api.create_dms(guild_id=guild_id, user_id=uid)
                target_id = f"{target_direct_prefix}|{dms['guild_id']}"
                target_from = target_direct_prefix
            else:
                # 群成员与单聊用户共用同一个 openid，直接经由单聊通道发送
                target_id = f"{target_c2c_prefix}|{uid}"
                target_from = target_c2c_prefix

            # 显式指定基类：主动消息所用的子类会将发送放入冷却队列并返回 None，无法取得消息 ID
            return await QQBotContextManager.send_message(
                cls.derive_private_session(session_info, target_id, target_from),
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

        target = _reply_target(session_info)
        if target.scope == "dm":
            return
        client = _get_client()
        for msg_id in message_id:
            try:
                await client.recall_message(target, msg_id, hidetip=target.scope == "channel")
                Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to delete message {msg_id} in session {session_info.session_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if session_info.target_from == target_guild_prefix:
            emoji_type = 1 if int(qq_typing_emoji) < 9000 else 2
            client = _get_client()

            try:
                await client.api.put_reaction(
                    channel_id=session_info.get_common_target_id(),
                    message_id=message_id[-1],
                    emoji_type=emoji_type,
                    emoji_id=emoji,
                )
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

        if session_info.target_from == target_guild_prefix:
            emoji_type = 1 if int(qq_typing_emoji) < 9000 else 2
            client = _get_client()

            try:
                await client.api.delete_reaction(
                    channel_id=session_info.get_common_target_id(),
                    message_id=message_id[-1],
                    emoji_type=emoji_type,
                    emoji_id=emoji,
                )
                Logger.info(f'Removed reaction "{emoji}" to message {message_id} in session {session_info.session_id}')
            except Exception:
                Logger.exception(
                    f'Failed to remove reaction "{emoji}" to message {message_id} in session {
                        session_info.session_id
                    }: '
                )

    @classmethod
    def _on_message_sent(cls, session_info: SessionInfo) -> None:
        """登记平台已经成功接受该会话中的普通消息。"""
        state = cls.typing_states.get(session_info.session_id)
        if state:
            state.spoken.set()

    @classmethod
    def _on_message_sending(cls, session_info: SessionInfo) -> None:
        """登记普通消息已完成资源准备，即将进入平台消息发送阶段。"""
        state = cls.typing_states.get(session_info.session_id)
        if state:
            state.sending.set()

    @staticmethod
    async def _wait_typing_over(state: _TypingState, timeout: float) -> bool:
        """等待输入状态结束或普通回复进入发送阶段，取先到者。

        :param state: 本轮输入状态的标志。
        :param timeout: 最长等待秒数。
        :return: 是否在超时之前等到了其中一个信号。
        """
        waiters = [asyncio.ensure_future(state.finished.wait()), asyncio.ensure_future(state.sending.wait())]
        try:
            done, _ = await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            return bool(done)
        finally:
            for waiter in waiters:
                waiter.cancel()

    @classmethod
    async def _guild_typing(cls, session_info: SessionInfo, state: _TypingState) -> None:
        """频道支持表情回应，直接以一枚回应表示正在处理。

        :param session_info: 目标会话。
        :param state: 本轮输入状态的标志。
        """
        client = _get_client()
        emoji_type = 1 if int(qq_typing_emoji) < 9000 else 2
        try:
            await client.api.put_reaction(
                channel_id=session_info.get_common_target_id(),
                message_id=session_info.message_id,
                emoji_type=emoji_type,
                emoji_id=qq_typing_emoji,
            )
        except Exception:
            Logger.exception(f"Failed to add typing reaction in session {session_info.session_id}: ")
        await cls._wait_typing_over(state, cls.TYPING_PROMPT_MAX_LIFETIME)

    @classmethod
    async def _c2c_typing(cls, session_info: SessionInfo, state: _TypingState) -> None:
        """好友消息使用 botpy 提供的原生输入状态通知。"""
        client = _get_client()
        context = cls.context.get(session_info.session_id)
        target = _reply_target(session_info, context)
        del context
        try:
            await client.send_typing(
                target,
                duration_seconds=cls.TYPING_PROMPT_MAX_LIFETIME,
            )
        except Exception:
            Logger.exception(f"Failed to send C2C typing state in session {session_info.session_id}: ")
        await cls._wait_typing_over(state, cls.TYPING_PROMPT_MAX_LIFETIME)

    @classmethod
    async def _group_typing(cls, session_info: SessionInfo, state: _TypingState) -> None:
        """群聊没有原生输入状态，改以一条提示消息模拟，并保证其终将被撤回。

        :param session_info: 目标会话。
        :param state: 本轮输入状态的标志。
        """
        typing_msg = None
        prepare_task = None
        state_waiter = None
        try:
            elements = [I18NContext("message.typing")]
            if CoreConfig.use_emote:
                if TYPING_EMOTES:
                    elements.append(Image(Random.choice(TYPING_EMOTES)))
                else:
                    Logger.warning(
                        f"QQBot typing emote is enabled but no GIF resources were found in {TYPING_EMOTE_DIR}."
                    )
            typing_message = MessageChain.assign(elements)
            prepare_started_at = time.monotonic()
            prepare_task = asyncio.create_task(
                cls._prepare_message(
                    session_info,
                    typing_message,
                    _ignore_retries=True,
                    _typing_prompt=True,
                    _force_plain=typing_message.contains(ImageElement),
                    quote=False,
                ),
                name=f"qqbot-typing-prepare-{session_info.session_id}",
            )
            state_waiter = asyncio.create_task(
                cls._wait_typing_over(state, cls.TYPING_PROMPT_MAX_LIFETIME),
                name=f"qqbot-typing-prepare-wait-{session_info.session_id}",
            )
            done, _ = await asyncio.wait((prepare_task, state_waiter), return_when=asyncio.FIRST_COMPLETED)
            if state_waiter in done and state_waiter.result():
                prepare_task.cancel()
                await asyncio.gather(prepare_task, return_exceptions=True)
                return

            prepared = await prepare_task
            state_waiter.cancel()
            await asyncio.gather(state_waiter, return_exceptions=True)

            # 延时从 start_typing 信号开始计算；图片读取与 upload_media 不会额外
            # 把提示发送时间向后推，从而避免资源准备慢于普通回复时 typing 后发。
            remaining_delay = max(0.0, cls.TYPING_PROMPT_DELAY - (time.monotonic() - prepare_started_at))
            if await cls._wait_typing_over(state, remaining_delay):
                return
            if state.finished.is_set() or state.sending.is_set():
                return

            typing_msg = await cls._send_prepared_message(
                session_info,
                prepared,
                _typing_prompt=True,
                _typing_state=state,
            )
            Logger.debug(f"Typing prompt sent in session {session_info.session_id}: {typing_msg}")

            # 机器人发言或输入状态结束时均可撤回，并由最长存活时间处理信号丢失。
            await cls._wait_typing_over(state, cls.TYPING_PROMPT_MAX_LIFETIME)
        except Exception:
            Logger.exception(f"Failed to show typing prompt in session {session_info.session_id}: ")
        finally:
            if state_waiter and not state_waiter.done():
                state_waiter.cancel()
                await asyncio.gather(state_waiter, return_exceptions=True)
            if prepare_task and not prepare_task.done():
                prepare_task.cancel()
                await asyncio.gather(prepare_task, return_exceptions=True)
            # 撤回置于 finally：异常与任务取消同样不得使提示消息滞留于群中。
            # 撤回自身再失败也只作记录，不使本轮任务带着异常收场。
            if typing_msg:
                try:
                    await cls.delete_message(session_info, typing_msg)
                except Exception:
                    Logger.exception(f"Failed to recall typing prompt in session {session_info.session_id}: ")

    @classmethod
    async def _typing_lifecycle(cls, session_info: SessionInfo, state: _TypingState) -> None:
        """按会话来源执行一轮输入状态，并在结束后回收其登记。

        :param session_info: 目标会话。
        :param state: 本轮输入状态的标志。
        """
        try:
            async with asyncio.timeout(cls.TYPING_PROMPT_DELAY + cls.TYPING_PROMPT_MAX_LIFETIME + 10):
                if session_info.target_from == target_guild_prefix:
                    await cls._guild_typing(session_info, state)
                elif session_info.target_from == target_group_prefix:
                    await cls._group_typing(session_info, state)
                elif session_info.target_from == target_c2c_prefix:
                    await cls._c2c_typing(session_info, state)
                else:
                    await cls._wait_typing_over(state, cls.TYPING_PROMPT_MAX_LIFETIME)
        except TimeoutError:
            Logger.debug(f"Typing state expired in session: {session_info.session_id}")
        finally:
            # 结束信号若始终未至，状态不应长期滞留；仅回收本轮，避免误删后来者
            if cls.typing_states.get(session_info.session_id) is state:
                del cls.typing_states[session_info.session_id]
            current_task = asyncio.current_task()
            if cls.typing_tasks.get(session_info.session_id) is current_task:
                cls.typing_tasks.pop(session_info.session_id, None)

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        if cls._shutting_down:
            return
        if session_info.session_id not in cls.context:
            Logger.warning(f"Session {session_info.session_id} not found in context, skipped typing.")
            return
        Logger.debug(f"Start typing in session: {session_info.session_id}")

        # 同一会话重复开启时先结束上一轮，否则其提示消息将失去撤回时机。
        # 不可直接取消任务：平台可能已接受发送请求但尚未返回消息 ID；取消后提示仍会
        # 留在群聊中，且无法取得用于撤回的 ID。
        previous = cls.typing_states.pop(session_info.session_id, None)
        if previous:
            previous.finished.set()
        previous_task = cls.typing_tasks.pop(session_info.session_id, None)
        if previous_task:
            await asyncio.shield(asyncio.gather(previous_task, return_exceptions=True))

        state = _TypingState()
        cls.typing_states[session_info.session_id] = state
        cls.typing_tasks[session_info.session_id] = asyncio.create_task(
            cls._typing_lifecycle(session_info, state),
            name=f"qqbot-typing-{session_info.session_id}",
        )

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # 结束输入状态属于清理动作，须幂等且容错：此时上下文可能已被回收，
        # 若在此抛错，提示消息将连撤回的机会都没有。
        state = cls.typing_states.pop(session_info.session_id, None)
        if state:
            state.finished.set()
        task = cls.typing_tasks.pop(session_info.session_id, None)
        if task:
            # 让正在发送的提示取得消息 ID 后自行进入 finally 撤回。直接取消可能造成
            # 「平台已发出、SDK 未返回 ID」的孤儿提示消息。
            await asyncio.shield(asyncio.gather(task, return_exceptions=True))
        Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if session_info.target_from == target_guild_prefix:
            emoji_type = 1 if int(qq_limited_emoji) < 9000 else 2
            client = _get_client()

            await client.api.put_reaction(
                channel_id=session_info.get_common_target_id(),
                message_id=session_info.message_id,
                emoji_type=emoji_type,
                emoji_id=qq_limited_emoji,
            )

    @classmethod
    async def restrict_member(
        cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None = None, reason: str | None = None
    ) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from == target_group_prefix:
            client = _get_client()
            duration = datetime.now(timezone.utc) + timedelta(seconds=duration if duration else 60)

            rdata = [
                SetMemberMuteState(
                    op="add",
                    member_openid=u.removeprefix(session_info.sender_from + "|"),
                    mute_expire_at=duration.isoformat(),
                )
                for u in user_id
            ]
            Logger.debug(rdata)
            await client.api.set_group_member_mutes(session_info.get_common_target_id(), rdata)

    @classmethod
    async def unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from == target_group_prefix:
            client = _get_client()
            await client.api.set_group_member_mutes(
                session_info.get_common_target_id(),
                [
                    SetMemberMuteState(
                        op="del", member_openid=u.removeprefix(session_info.sender_from + "|"), mute_expire_at=""
                    )
                    for u in user_id
                ],
            )

    @classmethod
    async def grant_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        await cls._edit_permission_groups(session_info, user_id, permission_group_id, grant=True)

    @classmethod
    async def revoke_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        await cls._edit_permission_groups(session_info, user_id, permission_group_id, grant=False)

    @staticmethod
    async def _edit_permission_groups(
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        grant: bool,
    ) -> None:
        if session_info.target_from != target_guild_prefix:
            return
        user_ids = [user_id] if isinstance(user_id, str) else user_id
        group_ids = [permission_group_id] if isinstance(permission_group_id, str) else permission_group_id
        if not isinstance(user_ids, list) or not isinstance(group_ids, list):
            raise TypeError("User ID and permission group ID must be a list or str")

        target_parts = session_info.target_id.removeprefix(f"{target_guild_prefix}|").split("|", 1)
        guild_id = target_parts[0]
        channel_id = target_parts[1] if len(target_parts) > 1 else None
        client = _get_client()
        for uid in user_ids:
            member_id = str(uid).split("|")[-1]
            for group_id in group_ids:
                role_id = str(group_id).split("|")[-1]
                if grant:
                    await client.api.create_guild_role_member(guild_id, role_id, member_id, channel_id)
                else:
                    await client.api.delete_guild_role_member(guild_id, role_id, member_id, channel_id)
        action = "Granted" if grant else "Revoked"
        Logger.info(f"{action} permission groups {group_ids} for members {user_ids} in guild {guild_id}")


_tasks_high_priority = deque()
_tasks = deque()


class QQBotFetchedContextManager(QQBotContextManager):
    _processor_task: asyncio.Task[None] | None = None
    _high_priority_count = 0

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        _ignore_retries: bool = False,
        _typing_prompt: bool = False,
        _force_plain: bool = False,
    ) -> list[str]:
        # 主动消息须按冷却排队发出，但调用方需要取得真实的消息 ID 才能判断本跳是否送达，
        # 因此入队的是「任务 + future」，待实际发送完成后再回传结果。
        future = asyncio.get_running_loop().create_future()
        high_priority = session_info.target_union_info.target_data.get("in_post_whitelist", False)
        append_tsk = _tasks_high_priority if high_priority else _tasks
        queue_size = len(_tasks_high_priority) + len(_tasks)
        if not high_priority and queue_size >= INITIATIVE_QUEUE_MAX_SIZE - HIGH_PRIORITY_QUEUE_RESERVE:
            Logger.warning(f"QQBot initiative message queue is full; dropped message to {session_info.target_id}.")
            return []
        if high_priority and queue_size >= INITIATIVE_QUEUE_MAX_SIZE:
            if _tasks:
                evicted_future = _tasks.popleft()[0]
                if not evicted_future.done():
                    evicted_future.set_result([])
            else:
                Logger.warning(
                    f"QQBot high-priority initiative message queue is full; dropped message to {session_info.target_id}."
                )
                return []
        task = (
            future,
            session_info,
            message,
            quote,
            _ignore_retries,
            _typing_prompt,
            _force_plain,
        )
        append_tsk.append(task)
        try:
            return await future
        finally:
            if future.cancelled():
                try:
                    append_tsk.remove(task)
                except ValueError:
                    pass

    @staticmethod
    async def _run_task(task: tuple) -> None:
        future, session_info, message, quote, _ignore_retries, _typing_prompt, _force_plain = task
        if future.cancelled():
            return
        try:
            result = await QQBotContextManager.send_message(
                session_info,
                message,
                quote=quote,
                _ignore_retries=_ignore_retries,
                _typing_prompt=_typing_prompt,
                _force_plain=_force_plain,
            )
        except asyncio.CancelledError:
            if not future.done():
                future.cancel()
            raise
        except Exception:
            Logger.exception(f"Failed to post message to {session_info.target_id}: ")
            result = []
        if not future.done():
            future.set_result(result)

    @classmethod
    def _take_next_task(cls) -> tuple[tuple, bool] | None:
        if _tasks_high_priority and (not _tasks or cls._high_priority_count < HIGH_PRIORITY_BURST):
            cls._high_priority_count += 1
            return _tasks_high_priority.popleft(), True
        if _tasks:
            cls._high_priority_count = 0
            return _tasks.popleft(), False
        cls._high_priority_count = 0
        return None

    @classmethod
    def start_task_processor(cls) -> asyncio.Task[None]:
        if cls._processor_task is None or cls._processor_task.done():
            if cls._processor_task and not cls._processor_task.cancelled():
                cls._processor_task.exception()
            cls._processor_task = asyncio.create_task(cls.process_tasks(), name="qqbot-initiative-message-worker")
        return cls._processor_task

    @classmethod
    async def stop_task_processor(cls) -> None:
        """停止主动消息 worker，并让尚未处理的调用方收到发送失败。"""
        task = cls._processor_task
        cls._processor_task = None
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        for queue in (_tasks_high_priority, _tasks):
            while queue:
                future = queue.popleft()[0]
                if future is not None and not future.done():
                    future.set_result([])
        cls._high_priority_count = 0

    @staticmethod
    async def process_tasks():
        # https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html
        # 60 qpm

        while True:
            try:
                queued_task = QQBotFetchedContextManager._take_next_task()
                if queued_task is None:
                    await asyncio.sleep(1)
                    continue
                task, high_priority = queued_task
                await QQBotFetchedContextManager._run_task(task)
                cd = 1 if high_priority else 1.5
                priority = "high-priority " if high_priority else ""
                Logger.info(f"Processed a {priority}task in QQBotFetchedContextManager, waiting cooldown for {cd}s...")
                await asyncio.sleep(cd)
            except asyncio.CancelledError:
                raise
            except Exception:
                Logger.exception("QQBot initiative message worker failed to process a task: ")
