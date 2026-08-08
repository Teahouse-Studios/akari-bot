import asyncio
import html
from urllib.parse import quote

import orjson
from botpy.api import BotAPI
from botpy.errors import ServerError
from botpy.http import Route
from botpy.interaction import Interaction
from botpy.message import BaseMessage, C2CMessage, DirectMessage, GroupMessage, Message
from botpy.types.message import Media, Reference, MarkdownPayload, KeyboardPayload
from botpy.types.inline import Keyboard, Button, KeyboardRow, RenderData, Action, Permission
from tenacity import retry, retry_if_exception, wait_fixed, stop_after_attempt

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
from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import ActionTextElement, PlainElement, ImageElement, MentionElement, URLElement
from core.builtins.message.internal import I18NContext
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from bots.qqbot.config import QQBotConfig
from core.logger import Logger
from core.utils.s3 import S3Storage
from core.utils.table import escape_table_cell, resolve_table_columns

qq_typing_emoji = str(QQBotConfig.qq_typing_emoji)
qq_limited_emoji = str(QQBotConfig.qq_limited_emoji)
qq_use_markdown = QQBotConfig.qq_use_markdown

global_seq = 1

# 平台判定同一 msg_seq 重复投递时的报错文案
MSG_DEDUP_ERROR = "消息被去重，请检查请求msgseq"


def is_msg_dedup_error(e: BaseException) -> bool:
    """
    判断异常是否为平台的消息去重报错。

    仅此一种错误值得重试：每次发送前 ``global_seq`` 都会自增，换一个序号重发即可成功。
    其余 ServerError（如参数非法、频率限制、权限不足）重试同样会失败，
    应当原样抛出交由上层处理，既不该重试，也不该被静默吞掉。

    :param e: 待判断的异常。
    """
    return isinstance(e, ServerError) and e.msgs == MSG_DEDUP_ERROR


# 平台对指令操作标签内文本的字符数上限，按 urlencode 前的原文计算
ACTION_TEXT_MAX_LENGTH = 100


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


# 节点表格的高度上限，按「编号行 + 内容行」计对。过宽的表格平台会渲染失败，故此值宜小不宜大：
# 每多一对，列数减半、单行长度随之减半。帮助的表格另有自己的上限，两者不共用。
MESSAGE_NODES_MAX_ROWS = 2


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


# 用户权限缓存，用于部分场景接口未返回群聊内身份使用
permission_cache = {}


# 额外添加平台接口支持但 SDK 不支持的方法
# https://github.com/tencent-connect/botpy/pull/215
class ModdedBotAPI(BotAPI):
    async def recall_group_message(self, group_openid: str, message_id: str) -> str:
        route = Route(
            "DELETE",
            "/v2/groups/{group_openid}/messages/{message_id}",
            group_openid=group_openid,
            message_id=message_id,
        )
        return await self._http.request(route)

    async def post_group_file(
        self,
        group_openid: str,
        file_type: int,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: str | None = None,
    ) -> Media:
        payload = locals()
        payload.pop("self", None)
        route = Route("POST", "/v2/groups/{group_openid}/files", group_openid=group_openid)
        return await self._http.request(route, json=payload)

    async def post_c2c_file(
        self,
        openid: str,
        file_type: int,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: str | None = None,
    ) -> Media:
        payload = locals()
        payload.pop("self", None)
        route = Route("POST", "/v2/users/{openid}/files", openid=openid)
        return await self._http.request(route, json=payload)


class _TypingState:
    """一轮输入状态的生命周期标志。

    群聊的输入提示是一条真实消息，撤回时机取决于两件事先发生哪一件：机器人发出了
    自身消息，或输入状态被显式结束。两个标志各自对应其一，由等待方取先到者。
    """

    __slots__ = ("finished", "spoken")

    def __init__(self):
        self.finished = asyncio.Event()
        self.spoken = asyncio.Event()


class QQBotContextManager(ContextManager):
    context: dict[str, BaseMessage] = {}
    features: Features = qqbot_features
    typing_states: dict[str, _TypingState] = {}

    # 机器人沉默满此秒数后，才在群聊中补发输入提示
    TYPING_PROMPT_DELAY = 5
    # 输入提示的最长存活秒数，用于在结束信号丢失时兜底撤回，避免提示消息永久滞留
    TYPING_PROMPT_MAX_LIFETIME = 60

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: BaseMessage):
        from bots.qqbot.bot import client

        context._api = ModdedBotAPI(http=client.http)
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
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
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
                return permission_cache.get(f"{session_info.target_id}|{session_info.sender_id}", False)
        return False

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
        _ignore_retries: bool = False,
        _typing_prompt: bool = False,
    ) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        ctx: BaseMessage | None = cls.context.get(session_info.session_id)
        # 输入提示本身不计作机器人发言，否则它一发出就会立即满足自己的撤回条件
        msg_ids = []
        global global_seq

        refid = None
        if ctx is not None and not isinstance(ctx, Interaction):
            if ctx.message_scene is not None:
                r = ctx.message_scene.get("ext")
                if r:
                    if r[0].startswith("msg_idx=REFIDX"):
                        refid = r[0].replace("msg_idx=", "")

        force_markdown = session_info.tmp.get("force_markdown") == "true"
        if isinstance(message, MessageNodes):
            message = MessageChain.assign(PlainElement.assign(nodes_to_table(session_info, message), disable_joke=True))
            force_markdown = True

        retry_attempt = stop_after_attempt(0)
        retry_wait = wait_fixed(0)
        if not _ignore_retries:
            retry_attempt = stop_after_attempt(3)
            retry_wait = wait_fixed(3)

        @retry(stop=retry_attempt, wait=retry_wait, retry=retry_if_exception(is_msg_dedup_error), reraise=True)
        async def send_msg():
            global global_seq

            plains: list[PlainElement] = []
            images: list[ImageElement] = []

            for x in message.as_sendable(session_info, parse_message=enable_parse_message, disable_markdown=True):
                if isinstance(x, PlainElement):
                    x.text = html.unescape(x.text)
                    if enable_parse_message:
                        x.text = match_atcode(x.text, client_name, "<@{uid}>")
                    plains.append(x)
                elif isinstance(x, ImageElement):
                    images.append(x)
                elif isinstance(x, MentionElement):
                    if x.client == client_name and session_info.target_from == target_guild_prefix:
                        plains.append(PlainElement(text=f"<@{x.id}>"))
            if len(plains + images) != 0:
                msg = "\n".join([x.text for x in plains]).strip()
                image_1 = None
                send_img = None

                if ctx and not isinstance(ctx, Interaction):
                    if isinstance(ctx, Message):
                        if images:
                            image_1 = images[0]
                            images.pop(0)
                        send_img = await image_1.get() if image_1 else None
                        msg_quote = (
                            Reference(
                                message_id=refid,
                                ignore_get_message_error=False,
                            )
                            if quote and refid is not None and not send_img
                            else None
                        )
                        msg = url_filter(msg)
                        if not msg_quote and quote:
                            msg = f"<@{ctx.author.id}> \n" + msg
                        msg = "" if not msg else msg
                        send = await ctx.reply(content=msg, file_image=send_img, message_reference=msg_quote)
                        if not _typing_prompt:
                            cls._on_message_sent(session_info)
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if image_1:
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                        if send:
                            msg_ids.append(send["id"])
                        if images:
                            for img in images:
                                send_img = await img.get()
                                send = await ctx.reply(file_image=send_img)
                                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                                if send:
                                    msg_ids.append(send["id"])
                    elif isinstance(ctx, DirectMessage):
                        if images:
                            image_1 = images[0]
                            images.pop(0)
                        send_img = await image_1.get() if image_1 else None
                        msg_quote = (
                            Reference(
                                message_id=refid,
                                ignore_get_message_error=False,
                            )
                            if quote and refid is not None and not send_img
                            else None
                        )
                        msg = url_filter(msg)
                        msg = "" if not msg else msg
                        send = await ctx.reply(content=msg, file_image=send_img, message_reference=msg_quote)
                        if not _typing_prompt:
                            cls._on_message_sent(session_info)
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if image_1:
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                        if send:
                            msg_ids.append(send["id"])
                        if images:
                            for img in images:
                                send_img = await img.get()
                                send = await ctx.reply(file_image=send_img)
                                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                                if send:
                                    msg_ids.append(send["id"])
                    elif isinstance(ctx, GroupMessage):
                        msg_quote = (
                            Reference(
                                message_id=refid,
                                ignore_get_message_error=False,
                            )
                            if quote and refid is not None and not send_img
                            else None
                        )
                        if msg and ctx.id and session_info.tmp.get("message_type") == "group_at":
                            msg = "\n" + msg
                        msg = "" if not msg else msg
                        if images:
                            image_1 = images[0]
                            images.pop(0)
                            send_img = await ctx._api.post_group_file(
                                group_openid=ctx.group_openid,
                                file_type=1,
                                file_data=await image_1.get_base64(),
                            )
                        global_seq += 1
                        send = await ctx.reply(
                            content=msg,
                            msg_type=7 if send_img else 0,
                            media=send_img,
                            msg_seq=global_seq,
                            message_reference=msg_quote,
                        )
                        if not _typing_prompt:
                            cls._on_message_sent(session_info)
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                        if image_1:
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                        if send:
                            msg_ids.append(send["id"])

                        if images:
                            for img in images:
                                send_img = await ctx._api.post_group_file(
                                    group_openid=ctx.group_openid,
                                    file_type=1,
                                    file_data=await img.get_base64(),
                                )
                                global_seq += 1
                                send = await ctx.reply(msg_type=7, media=send_img, msg_seq=global_seq)
                                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                                if send:
                                    msg_ids.append(send["id"])

                    elif isinstance(ctx, C2CMessage):
                        if images:
                            image_1 = images[0]
                            images.pop(0)
                            send_img = await ctx._api.post_c2c_file(
                                openid=ctx.author.user_openid,
                                file_type=1,
                                file_data=await image_1.get_base64(),
                            )
                        msg = "" if not msg else msg
                        global_seq += 1
                        send = await ctx.reply(
                            content=msg,
                            msg_type=7 if send_img else 0,
                            media=send_img,
                            msg_seq=global_seq,
                        )
                        if not _typing_prompt:
                            cls._on_message_sent(session_info)
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                        if image_1:
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                        if send:
                            msg_ids.append(send["id"])

                        if images:
                            for img in images:
                                send_img = await ctx._api.post_c2c_file(
                                    openid=ctx.author.user_openid,
                                    file_type=1,
                                    file_data=await img.get_base64(),
                                )
                                global_seq += 1
                                send = await ctx.reply(msg_type=7, media=send_img, msg_seq=global_seq)
                                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                                if send:
                                    msg_ids.append(send["id"])
                else:
                    from bots.qqbot.bot import client

                    client.api = ModdedBotAPI(http=client.http)

                    if session_info.target_from == target_guild_prefix:
                        if images:
                            image_1 = images[0]
                            images.pop(0)
                        send_img = await image_1.get() if image_1 else None
                        msg = url_filter(msg)
                        msg = "" if not msg else msg
                        send = await client.api.post_message(
                            channel_id=session_info.get_common_target_id(),
                            content=msg,
                            file_image=send_img,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if image_1:
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                        if send:
                            msg_ids.append(send["id"])
                        if images:
                            for img in images:
                                send_img = await img.get()
                                send = await client.api.post_message(
                                    channel_id=session_info.get_common_target_id(), file_image=send_img
                                )
                                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                                if send:
                                    msg_ids.append(send["id"])
                    elif session_info.target_from == target_direct_prefix:
                        if images:
                            image_1 = images[0]
                            images.pop(0)
                        send_img = await image_1.get() if image_1 else None
                        msg = url_filter(msg)
                        msg = "" if not msg else msg
                        send = await client.api.post_dms(
                            guild_id=session_info.get_common_target_id(), content=msg, file_image=send_img
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if image_1:
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                        if send:
                            msg_ids.append(send["id"])
                        if images:
                            for img in images:
                                send_img = await img.get()
                                send = await client.api.post_dms(
                                    guild_id=session_info.get_common_target_id(), file_image=send_img
                                )
                                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                                if send:
                                    msg_ids.append(send["id"])
                    elif session_info.target_from == target_group_prefix:
                        msg = "" if not msg else msg
                        if images:
                            image_1 = images[0]
                            images.pop(0)
                            send_img = await client.api.post_group_file(
                                group_openid=session_info.get_common_target_id(),
                                file_type=1,
                                file_data=await image_1.get_base64(),
                            )
                        global_seq += 1
                        send = await client.api.post_group_message(
                            group_openid=session_info.get_common_target_id(),
                            content=msg,
                            msg_type=7 if send_img else 0,
                            media=send_img,
                            msg_seq=global_seq,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                        if image_1:
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                        if send:
                            msg_ids.append(send["id"])

                        if images:
                            for img in images:
                                send_img = await client.api.post_group_file(
                                    group_openid=session_info.get_common_target_id(),
                                    file_type=1,
                                    file_data=await img.get_base64(),
                                )
                                global_seq += 1
                                send = await client.api.post_group_message(
                                    group_openid=session_info.get_common_target_id(),
                                    msg_type=7,
                                    media=send_img,
                                    msg_seq=global_seq,
                                )
                                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                                if send:
                                    msg_ids.append(send["id"])

                    elif session_info.target_from == target_c2c_prefix:
                        if images:
                            image_1 = images[0]
                            images.pop(0)
                            send_img = await client.api.post_c2c_file(
                                openid=session_info.get_common_target_id(),
                                file_type=1,
                                file_data=await image_1.get_base64(),
                            )
                        msg = "" if not msg else msg
                        global_seq += 1
                        send = await client.api.post_c2c_message(
                            openid=session_info.get_common_target_id(),
                            content=msg,
                            msg_type=7 if send_img else 0,
                            media=send_img,
                            msg_seq=global_seq,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                        if image_1:
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                        if send:
                            msg_ids.append(send["id"])
                        if images:
                            for img in images:
                                send_img = await client.api.post_c2c_file(
                                    openid=session_info.get_common_target_id(),
                                    file_type=1,
                                    file_data=await img.get_base64(),
                                )
                                global_seq += 1
                                send = await client.api.post_c2c_message(
                                    openid=session_info.get_common_target_id(),
                                    msg_type=7,
                                    media=send_img,
                                    msg_seq=global_seq,
                                )
                                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                                if send:
                                    msg_ids.append(send["id"])

        @retry(stop=retry_attempt, wait=retry_wait, retry=retry_if_exception(is_msg_dedup_error), reraise=True)
        async def send_msg_markdown():
            global global_seq
            texts = []

            if quote and isinstance(ctx, (Message, GroupMessage)):
                texts.append(f'<qqbot-at-user id="{session_info.get_common_sender_id()}" />')
            keyboard = None
            if session_info.tmp.get("wait_type") == "wait_confirm" and session_info.tmp.get("wait_active") == "yes":
                button_yes = Button(
                    id="1",
                    render_data=RenderData(
                        label=session_info.locale.t("message.button.yes"),
                        visited_label=session_info.locale.t("message.confirmed"),
                        style=0,
                    ),
                    action=Action(
                        type=1,
                        permission=Permission(
                            type=0 if not isinstance(ctx, C2CMessage) else 2,
                            specify_user_ids=[session_info.get_common_sender_id()],
                            specify_role_ids=["1"],
                        ),
                        click_limit=1,
                        data="confirm_yes",
                        at_bot_show_channel_list=False,
                    ),
                )
                button_no = Button(
                    id="2",
                    render_data=RenderData(
                        label=session_info.locale.t("message.button.no"),
                        visited_label=session_info.locale.t("message.cancelled"),
                        style=0,
                    ),
                    action=Action(
                        type=1,
                        permission=Permission(
                            type=0 if not isinstance(ctx, C2CMessage) else 2,
                            specify_user_ids=[session_info.get_common_sender_id()],
                            specify_role_ids=["1"],
                        ),
                        click_limit=1,
                        data="confirm_no",
                        at_bot_show_channel_list=False,
                    ),
                )

                keyboard = KeyboardPayload(content=Keyboard(rows=[KeyboardRow(buttons=[button_yes, button_no])]))

            possibly_choices: list[dict[str, str]] = []
            if session_info.tmp.get("button_data"):
                possibly_choices: list[dict[str, str]] = orjson.loads(session_info.tmp.get("button_data", ""))
            if (
                session_info.tmp.get("wait_type") == "wait_next_message"
                and session_info.tmp.get("wait_active") == "yes"
            ):
                possibly_choices: list[dict[str, str]] = orjson.loads(session_info.tmp.get("wait_possibly_choices", ""))
            if len(possibly_choices) > 0:
                rows = []
                i = 0
                for r in possibly_choices:
                    buttons = []

                    for label, data in r.items():
                        i += 1
                        button = Button(
                            id=str(i),
                            render_data=RenderData(
                                label=label, visited_label=session_info.locale.t("message.selected") + label, style=0
                            ),
                            action=Action(
                                type=1,
                                permission=Permission(
                                    type=0 if not isinstance(ctx, C2CMessage) else 2,
                                    specify_user_ids=[session_info.get_common_sender_id()],
                                    specify_role_ids=["1"],
                                ),
                                click_limit=1,
                                data=data,
                                at_bot_show_channel_list=False,
                            ),
                        )
                        buttons.append(button)
                    rows.append(KeyboardRow(buttons=buttons))
                keyboard = KeyboardPayload(content=Keyboard(rows=rows))

            converted_message = message.as_sendable(session_info, parse_message=enable_parse_message)
            _use_markdown = True

            if converted_message.only(PlainElement):
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
            if force_markdown:
                _use_markdown = True

            if not _use_markdown:
                Logger.debug("MessageElements do not require markdown, sending as plain message instead of markdown.")
                return await send_msg()

            # 指令操作是行内元素：它自身与紧随其后的文本都须并入上一项，
            # 否则 "\n".join(texts) 会把同属一句话的收尾文本甩到下一行
            inline_pending = False

            for x in converted_message:
                if isinstance(x, PlainElement):
                    x.text = html.unescape(x.text)
                    if enable_parse_message:
                        x.text = match_atcode(x.text, client_name, "<@{uid}>")
                    if inline_pending and texts:
                        texts[-1] += x.text
                    else:
                        texts.append(x.text)
                    inline_pending = False
                elif isinstance(x, ImageElement):
                    if S3Storage is not None:
                        upload = await S3Storage.upload_temp(await x.get())
                        if upload and "public_url" in upload:
                            w, h = await x.get_wh()
                            max_w = 128
                            fin_scale = max_w / w if w > max_w else 1
                            fin_w = w * fin_scale
                            fin_h = h * fin_scale
                            texts.append(f"![text #{int(fin_w)}px #{int(fin_h)}px]({upload['public_url']})")
                    inline_pending = False
                elif isinstance(x, MentionElement):
                    if x.client == client_name and session_info.target_from == target_guild_prefix:
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
            if len(texts) != 0:
                msg = "\n".join(texts)
                md = MarkdownPayload(content=msg)

                if ctx and not isinstance(ctx, Interaction):
                    if isinstance(ctx, (Message, DirectMessage, GroupMessage, C2CMessage)):
                        global_seq += 1
                        send = await ctx.reply(
                            markdown=md,
                            msg_type=2,
                            msg_seq=global_seq,
                            keyboard=keyboard,
                        )
                        if not _typing_prompt:
                            cls._on_message_sent(session_info)
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if send:
                            msg_ids.append(send["id"])

                else:
                    from bots.qqbot.bot import client

                    client.api = ModdedBotAPI(http=client.http)

                    if session_info.target_from == target_guild_prefix:
                        send = await client.api.post_message(
                            channel_id=session_info.get_common_target_id(),
                            markdown=md,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if send:
                            msg_ids.append(send["id"])

                    elif session_info.target_from == target_direct_prefix:
                        send = await client.api.post_dms(
                            guild_id=session_info.get_common_target_id(),
                            markdown=md,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if send:
                            msg_ids.append(send["id"])

                    elif session_info.target_from == target_group_prefix:
                        global_seq += 1
                        send = await client.api.post_group_message(
                            group_openid=session_info.get_common_target_id(),
                            markdown=md,
                            msg_type=2,
                            msg_seq=global_seq,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if send:
                            msg_ids.append(send["id"])

                    elif session_info.target_from == target_c2c_prefix:
                        global_seq += 1
                        send = await client.api.post_c2c_message(
                            openid=session_info.get_common_target_id(),
                            markdown=md,
                            msg_type=2,
                            msg_seq=global_seq,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                        if send:
                            msg_ids.append(send["id"])

        # 会话的 support_markdown 由 resolve_features() 按用户偏好置定，用户关闭 markdown 后
        # 走纯文本路径；全局配置关闭时同样如此。
        if not qq_use_markdown or not session_info.support_markdown:
            await send_msg()
        else:
            await send_msg_markdown()

        return msg_ids

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        from bots.qqbot.bot import client

        client.api = ModdedBotAPI(http=client.http)
        uid = user_id.split("|")[-1]

        try:
            if session_info.target_from == target_direct_prefix:
                # 当前已处于私信场景中，无需另行创建
                target_id, target_from = session_info.target_id, target_direct_prefix
            elif user_id.startswith(sender_tiny_prefix):
                # 频道用户的私信须先以来源频道创建私信场景，取得专用的 guild_id 后方可发送
                guild_id = session_info.target_id.split("|")[2]
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
                enable_parse_message=enable_parse_message,
                enable_split_image=enable_split_image,
            )
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

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        from bots.qqbot.bot import client

        client.api = ModdedBotAPI(http=client.http)
        if session_info.target_from == target_guild_prefix:
            for msg_id in message_id:
                try:
                    await client.api.recall_message(
                        channel_id=session_info.get_common_target_id(), message_id=msg_id, hidetip=True
                    )
                    Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
                except Exception:
                    Logger.exception(f"Failed to delete message {msg_id} in session {session_info.session_id}: ")
        elif session_info.target_from == target_group_prefix:
            for msg_id in message_id:
                try:
                    await client.api.recall_group_message(
                        group_openid=session_info.get_common_target_id(), message_id=msg_id
                    )
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

            from bots.qqbot.bot import client

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

            from bots.qqbot.bot import client

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
        """登记机器人已在该会话中发言。

        输入提示的意义是填补机器人迟迟不出声的空窗，机器人一经发言，提示便失去意义，
        应尽快撤回，故此处以发送动作驱动撤回，而非等到输入状态结束。

        :param session_info: 发出消息的会话。
        """
        state = cls.typing_states.get(session_info.session_id)
        if state:
            state.spoken.set()

    @staticmethod
    async def _wait_typing_over(state: _TypingState, timeout: float) -> bool:
        """等待输入状态结束或机器人发言，取先到者。

        :param state: 本轮输入状态的标志。
        :param timeout: 最长等待秒数。
        :return: 是否在超时之前等到了其中一个信号。
        """
        waiters = [
            asyncio.ensure_future(state.finished.wait()),
            asyncio.ensure_future(state.spoken.wait()),
        ]
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
        from bots.qqbot.bot import client

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
    async def _group_typing(cls, session_info: SessionInfo, state: _TypingState) -> None:
        """群聊没有原生输入状态，改以一条提示消息模拟，并保证其终将被撤回。

        :param session_info: 目标会话。
        :param state: 本轮输入状态的标志。
        """
        typing_msg = None
        try:
            # 机器人若在等待窗口内就已发言，空窗并未出现，无须补发提示
            if await cls._wait_typing_over(state, cls.TYPING_PROMPT_DELAY):
                return

            typing_msg = await cls.send_message(
                session_info,
                MessageChain.assign(I18NContext("message.typing")),
                _ignore_retries=True,
                _typing_prompt=True,
                quote=False,
            )
            Logger.debug(f"Typing prompt sent in session {session_info.session_id}: {typing_msg}")

            # 机器人发言或输入状态结束皆可撤回，另以最长存活兜底，防止结束信号丢失
            await cls._wait_typing_over(state, cls.TYPING_PROMPT_MAX_LIFETIME)
        except Exception:
            Logger.exception(f"Failed to show typing prompt in session {session_info.session_id}: ")
        finally:
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
            if session_info.target_from == target_guild_prefix:
                await cls._guild_typing(session_info, state)
            elif session_info.target_from == target_group_prefix:
                await cls._group_typing(session_info, state)
            else:
                await cls._wait_typing_over(state, cls.TYPING_PROMPT_MAX_LIFETIME)
        finally:
            # 结束信号若始终未至，状态不应长期滞留；仅回收本轮，避免误删后来者
            if cls.typing_states.get(session_info.session_id) is state:
                del cls.typing_states[session_info.session_id]

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            Logger.warning(f"Session {session_info.session_id} not found in context, skipped typing.")
            return
        Logger.debug(f"Start typing in session: {session_info.session_id}")

        # 同一会话重复开启时先结束上一轮，否则其提示消息将失去撤回时机
        previous = cls.typing_states.pop(session_info.session_id, None)
        if previous:
            previous.finished.set()

        state = _TypingState()
        cls.typing_states[session_info.session_id] = state
        asyncio.create_task(cls._typing_lifecycle(session_info, state))

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # 结束输入状态属于清理动作，须幂等且容错：此时上下文可能已被回收，
        # 若在此抛错，提示消息将连撤回的机会都没有。
        state = cls.typing_states.pop(session_info.session_id, None)
        if state:
            state.finished.set()
        Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加错误处理逻辑

        if session_info.target_from == target_guild_prefix:
            emoji_type = 1 if int(qq_limited_emoji) < 9000 else 2

            from bots.qqbot.bot import client

            await client.api.put_reaction(
                channel_id=session_info.get_common_target_id(),
                message_id=session_info.message_id,
                emoji_type=emoji_type,
                emoji_id=qq_limited_emoji,
            )


_tasks_high_priority = []
_tasks = []


class QQBotFetchedContextManager(QQBotContextManager):
    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        enable_parse_message=True,
        enable_split_image=True,
        _ignore_retries: bool = False,
        _typing_prompt: bool = False,
    ) -> list[str]:
        # 主动消息须按冷却排队发出，但调用方需要取得真实的消息 ID 才能判断本跳是否送达，
        # 因此入队的是「任务 + future」，待实际发送完成后再回传结果。
        future = asyncio.get_running_loop().create_future()
        append_tsk = (
            _tasks_high_priority
            if session_info.target_union_info.target_data.get("in_post_whitelist", False)
            else _tasks
        )
        append_tsk.append((future, session_info, message, quote, enable_parse_message, _ignore_retries, _typing_prompt))
        return await future

    @staticmethod
    async def _run_task(task: tuple) -> None:
        future, session_info, message, quote, enable_parse_message, _ignore_retries, _typing_prompt = task
        try:
            result = await QQBotContextManager.send_message(
                session_info,
                message,
                quote=quote,
                enable_parse_message=enable_parse_message,
                _ignore_retries=_ignore_retries,
                _typing_prompt=_typing_prompt,
            )
        except Exception:
            Logger.exception(f"Failed to post message to {session_info.target_id}: ")
            result = []
        if not future.done():
            future.set_result(result)

    @staticmethod
    async def process_tasks():
        # https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html
        # 60 qpm

        while True:
            if _tasks_high_priority:
                await QQBotFetchedContextManager._run_task(_tasks_high_priority.pop(0))
                cd = 1
                Logger.info(
                    f"Processed a high-priority task in QQBotFetchedContextManager, waiting cooldown for {cd}s..."
                )
                await asyncio.sleep(cd)
            elif _tasks:
                await QQBotFetchedContextManager._run_task(_tasks.pop(0))
                cd = 1.5
                Logger.info(f"Processed a task in QQBotFetchedContextManager, waiting cooldown for {cd}s...")
                await asyncio.sleep(cd)
            else:
                await asyncio.sleep(1)
