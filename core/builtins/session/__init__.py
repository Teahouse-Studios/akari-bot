from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import timedelta, datetime, UTC as datetimeUTC
from typing import Any, Optional, Union, TYPE_CHECKING, List, Match, Tuple, Coroutine, Dict

from attrs import define

from core.builtins.utils import confirm_command
from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.builtins.types import MessageElement
from core.config import Config
from core.constants import FinishedException, WaitCancelException
from core.database.models import TargetInfo, SenderInfo
from core.exports import add_export, exports
from core.i18n import Locale
from core.utils.text import parse_time_string


@define
class SessionInfo:
    target_id: str
    sender_id: Optional[str]
    sender_name: Optional[str]
    target_from: str
    sender_from: Optional[str]
    client_name: str
    message_id: Optional[str] = None
    reply_id: Optional[str] = None
    messages: Optional[MessageChain] = None
    admin: bool = False
    superuser: bool = False
    support_image: bool = False
    support_voice: bool = False
    support_mention: bool = False
    support_embed: bool = False
    support_forward: bool = False
    support_delete: bool = False
    support_markdown: bool = False
    support_quote: bool = False
    support_rss: bool = False
    support_typing: bool = False
    support_wait: bool = False


@define
class MessageSession:
    session_info: SessionInfo
    sent: List[MessageChain] = []
    trigger_msg: Optional[str] = ''
    matched_msg: Optional[Union[Match[str], Tuple[Any]]] = None
    parsed_msg: Optional[dict] = None
    prefixes: List[str] = []
    target_info: Optional[TargetInfo] = None
    sender_info: Optional[SenderInfo] = None
    muted: Optional[bool] = None
    sender_data: Optional[dict] = None
    target_data: Optional[dict] = None
    custom_admins: Optional[list] = None
    enabled_modules: Optional[dict] = None
    locale: Optional[Locale] = None
    bot_name: Optional[str] = None
    _tz_offset: Optional[str] = None
    timezone_offset: Optional[timedelta] = None
    petal: Optional[int] = None
    tmp = {}

    @classmethod
    async def from_session_info(cls, session: SessionInfo):
        get_target_info: TargetInfo = await TargetInfo.get_by_target_id(session.target_id)
        get_sender_info: SenderInfo = await SenderInfo.get_by_sender_id(session.sender_id) if session.sender_id else None
        locale = Locale(get_target_info.locale)
        _tz_offset = get_target_info.target_data.get("tz_offset", Config("timezone_offset", "+8"))
        return deepcopy(cls(
            session_info=session,
            target_info=get_target_info,
            sender_info=get_sender_info,
            muted=get_target_info.muted,
            target_data=get_target_info.target_data,
            sender_data=get_sender_info.sender_data if get_sender_info else None,
            custom_admins=get_target_info.custom_admins,
            enabled_modules=get_target_info.modules,
            locale=locale,
            bot_name=locale.t("bot_name"),
            tz_offset=_tz_offset,
            timezone_offset=parse_time_string(_tz_offset),
            petal=get_sender_info.petal if get_sender_info else None,
        ))

    async def send_message(
        self,
        message_chain: Union[MessageChain, str, list, MessageElement],
        quote: bool = True,
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
        callback: Optional[Coroutine] = None,
    ) -> FinishedSession:
        """
        用于向消息发送者返回消息。

        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链。
        :param quote: 是否引用传入dict中的消息。（默认为True）
        :param disable_secret_check: 是否禁用消息检查。（默认为False）
        :param enable_parse_message: 是否允许解析消息。（此参数作接口兼容用，仅QQ平台使用，默认为True）
        :param enable_split_image: 是否允许拆分图片发送。（此参数作接口兼容用，仅telegram平台使用，默认为True）
        :param callback: 回调函数，用于在消息发送完成后回复本消息执行的函数。
        :return: 被发送的消息链。
        """

        message_chain = converter.unstructure(message_chain)
        await exports["JobQueueServer"].send_message_to_client(self.session_info.client_name, self.session_info.target_id, message_chain)

        if callback:
            # todo: 此处临时引用了发送的指令的message_id，稍后更正
            SessionTaskManager.add_callback(self.session_info.message_id, callback)

    async def finish(
        self,
        message_chain: Optional[Union[MessageChain, str, list, MessageElement]] = None,
        quote: bool = True,
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
        callback: Optional[Coroutine] = None,
    ):
        """
        用于向消息发送者返回消息并终结会话（模块后续代码不再执行）。

        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链，可不填。
        :param quote: 是否引用传入dict中的消息。（默认为True）
        :param disable_secret_check: 是否禁用消息检查。（默认为False）
        :param enable_parse_message: 是否允许解析消息。（此参数作接口兼容用，仅QQ平台使用，默认为True）
        :param enable_split_image: 是否允许拆分图片发送。（此参数作接口兼容用，仅telegram平台使用，默认为True）
        :param callback: 回调函数，用于在消息发送完成后回复本消息执行的函数。
        :return: 被发送的消息链。
        """
        ...
        f = None
        if message_chain:
            f = await self.send_message(
                message_chain,
                disable_secret_check=disable_secret_check,
                quote=quote,
                enable_parse_message=enable_parse_message,
                enable_split_image=enable_split_image,
                callback=callback,
            )
        raise FinishedException(f)

    async def send_direct_message(
        self,
        message_chain: Union[MessageChain, str, list, MessageElement],
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
        callback: Optional[Coroutine] = None,
    ):
        """
        用于向消息发送者直接发送消息。

        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链。
        :param disable_secret_check: 是否禁用消息检查。（默认为False）
        :param enable_parse_message: 是否允许解析消息。（此参数作接口兼容用，仅QQ平台使用，默认为True）
        :param enable_split_image: 是否允许拆分图片发送。（此参数作接口兼容用，仅Telegram平台使用，默认为True）
        :param callback: 回调函数，用于在消息发送完成后回复本消息执行的函数。
        :return: 被发送的消息链。
        """
        await self.send_message(
            message_chain,
            disable_secret_check=disable_secret_check,
            quote=False,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
            callback=callback,
        )

    def as_display(self, text_only: bool = False) -> str:
        """
        用于将消息转换为一般文本格式。

        :param text_only: 是否只保留纯文本。（默认为False）
        :return: 转换后的字符串。
        """
        return self.session_info.messages.to_str(text_only)

    async def to_message_chain(self) -> MessageChain:
        """
        用于将session.message中的消息文本转换为MessageChain。

        :return: MessageChain消息。
        """
        raise NotImplementedError

    async def delete(self):
        """
        用于删除这条消息。
        """
        raise NotImplementedError

    async def check_native_permission(self) -> bool:
        """
        用于检查消息发送者原本在聊天平台中是否具有管理员权限。
        """
        return self.session_info.admin

    async def fake_forward_msg(self, nodelist: List[Dict[str, Union[str, Any]]]):
        """
        用于发送假转发消息（QQ）。

        :param nodelist: 消息段列表，即`type`键名为`node`的字典列表，详情参考OneBot文档。
        """
        raise NotImplementedError

    async def msgchain2nodelist(self, msg_chain_list: List[MessageChain], sender_name: Optional[str] = None,
                                ) -> list[Dict]:
        """
        用于将消息链列表转换为节点列表（QQ）。
        :param msg_chain_list: 消息链列表。
        :param sender_name: 用于指定发送者名称。
        """
        raise NotImplementedError

    async def get_text_channel_list(self) -> List[str]:
        """
        用于获取子文字频道列表（QQ）。
        """
        raise NotImplementedError

    class Typing:
        def __init__(self, msg: MessageSession):
            """
            :param msg: 本条消息，由于此class需要被一同传入下游方便调用，所以作为子class存在，将来可能会有其他的解决办法。
            """

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    async def call_api(self, action, **params):
        raise NotImplementedError

    async def wait_confirm(
        self,
        message_chain: Optional[Union[MessageChain, str, list, MessageElement]] = None,
        quote: bool = True,
        delete: bool = True,
        timeout: Optional[float] = 120,
        append_instruction: bool = True,
    ) -> bool:
        """
        一次性模板，用于等待触发对象确认。

        :param message_chain: 需要发送的确认消息，可不填。
        :param quote: 是否引用传入dict中的消息。（默认为True）
        :param delete: 是否在触发后删除消息。（默认为True）
        :param timeout: 超时时间。（默认为120）
        :param append_instruction: 是否在发送的消息中附加提示。
        :return: 若对象发送confirm_command中的其一文本时返回True，反之则返回False。
        """
        send = None
        ExecutionLockList.remove(self)
        if Config("no_confirm", False):
            return True
        if message_chain:
            message_chain = MessageChain(message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.wait.prompt.confirm"))
            send = await self.send_message(message_chain, quote)
        await asyncio.sleep(0.1)
        flag = asyncio.Event()
        SessionTaskManager.add_task(self, flag, timeout=timeout)
        try:
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        result = SessionTaskManager.get_result(self)
        if result:
            if send and delete:
                await send.delete()
            if result.as_display(text_only=True) in confirm_command:
                return True
            return False
        raise WaitCancelException

    async def wait_next_message(
        self,
        message_chain: Optional[Union[MessageChain, str, list, MessageElement]] = None,
        quote: bool = True,
        delete: bool = False,
        timeout: Optional[float] = 120,
        append_instruction: bool = True,
    ) -> MessageSession:
        """
        一次性模板，用于等待对象的下一条消息。

        :param message_chain: 需要发送的确认消息，可不填。
        :param quote: 是否引用传入dict中的消息。（默认为True）
        :param delete: 是否在触发后删除消息。（默认为False）
        :param timeout: 超时时间。（默认为120）
        :param append_instruction: 是否在发送的消息中附加提示。
        :return: 下一条消息的MessageChain对象。
        """
        send = None
        ExecutionLockList.remove(self)
        if message_chain:
            message_chain = MessageChain(message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.wait.prompt.next_message"))
            send = await self.send_message(message_chain, quote)
        await asyncio.sleep(0.1)
        flag = asyncio.Event()
        SessionTaskManager.add_task(self, flag, timeout=timeout)
        try:
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        result = SessionTaskManager.get_result(self)
        if send and delete:
            await send.delete()
        if result:
            return result
        raise WaitCancelException

    async def wait_reply(
        self,
        message_chain: Union[MessageChain, str, list, MessageElement],
        quote: bool = True,
        delete: bool = False,
        timeout: Optional[float] = 120,
        all_: bool = False,
        append_instruction: bool = True,
    ) -> MessageSession:
        """
        一次性模板，用于等待触发对象回复消息。

        :param message_chain: 需要发送的确认消息。
        :param quote: 是否引用传入dict中的消息。（默认为True）
        :param delete: 是否在触发后删除消息。（默认为False）
        :param timeout: 超时时间。（默认为120）
        :param all_: 是否设置触发对象为对象内的所有人。（默认为False）
        :param append_instruction: 是否在发送的消息中附加提示。
        :return: 回复消息的MessageChain对象。
        """
        self.tmp["enforce_send_by_master_client"] = True
        send = None
        ExecutionLockList.remove(self)
        message_chain = MessageChain(message_chain)
        if append_instruction:
            message_chain.append(I18NContext("message.reply.prompt"))
        send = await self.send_message(message_chain, quote)
        await asyncio.sleep(0.1)
        flag = asyncio.Event()
        SessionTaskManager.add_task(
            self, flag, reply=send.message_id, all_=all_, timeout=timeout
        )
        try:
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        result = SessionTaskManager.get_result(self)
        if send and delete:
            await send.delete()
        if result:
            return result
        raise WaitCancelException

    async def wait_anyone(
        self,
        message_chain: Optional[Union[MessageChain, str, list, MessageElement]] = None,
        quote: bool = False,
        delete: bool = False,
        timeout: Optional[float] = 120,
    ) -> MessageSession:
        """
        一次性模板，用于等待触发对象所属对话内任意成员确认。

        :param message_chain: 需要发送的确认消息，可不填。
        :param quote: 是否引用传入dict中的消息。（默认为False）
        :param delete: 是否在触发后删除消息。（默认为False）
        :param timeout: 超时时间。（默认为120）
        :return: 任意人的MessageChain对象。
        """
        send = None
        ExecutionLockList.remove(self)
        if message_chain:
            message_chain = MessageChain(message_chain)
            send = await self.send_message(message_chain, quote)
        await asyncio.sleep(0.1)
        flag = asyncio.Event()
        SessionTaskManager.add_task(self, flag, all_=True, timeout=timeout)
        try:
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        result = SessionTaskManager.get()[self.session_info.target_id]["all"][self]
        if "result" in result:
            if send and delete:
                await send.delete()
            return SessionTaskManager.get()[self.session_info.target_id]["all"][self][
                "result"
            ]
        raise WaitCancelException

    async def sleep(self, s: float):
        ExecutionLockList.remove(self)
        await asyncio.sleep(s)

    def check_super_user(self) -> bool:
        """
        用于检查消息发送者是否为超级用户。
        """
        return bool(self.sender_info.superuser)

    async def check_permission(self) -> bool:
        """
        用于检查消息发送者在对话内的权限。
        """
        if self.session_info.sender_id in self.custom_admins or self.sender_info.superuser:
            return True
        return await self.check_native_permission()

    waitConfirm = wait_confirm
    waitNextMessage = wait_next_message
    waitReply = wait_reply
    waitAnyone = wait_anyone
    checkPermission = check_permission
    checkSuperUser = check_super_user
    sendMessage = send_message
    sendDirectMessage = send_direct_message
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkNativePermission = check_native_permission

    def ts2strftime(
        self,
        timestamp: float,
        date: bool = True,
        iso: bool = False,
        time: bool = True,
        seconds: bool = True,
        timezone: bool = True,
    ) -> str:
        """
        用于将时间戳转换为可读的时间格式。

        :param timestamp: UTC时间戳。
        :param date: 是否显示日期。（默认为True）
        :param iso: 是否以ISO格式显示。（默认为False）
        :param time: 是否显示时间。（默认为True）
        :param seconds: 是否显示秒。（默认为True）
        :param timezone: 是否显示时区。（默认为True）
        :return: 格式化后的时间格式。
        """
        ftime_template = []
        if date:
            if iso:
                ftime_template.append(self.locale.t("time.date.iso.format"))
            else:
                ftime_template.append(self.locale.t("time.date.format"))
        if time:
            if seconds:
                ftime_template.append(self.locale.t("time.time.format"))
            else:
                ftime_template.append(self.locale.t("time.time.nosec.format"))
        if timezone:
            if self._tz_offset == "+0":
                ftime_template.append("(UTC)")
            else:
                ftime_template.append(f"(UTC{self._tz_offset})")
        return (
            datetime.fromtimestamp(timestamp, datetimeUTC) + self.timezone_offset
        ).strftime(" ".join(ftime_template))

    class Feature:
        """
        此消息来自的客户端所支持的消息特性一览，用于不同平台适用特性判断。
        """

        image = False
        voice = False
        mention = False
        embed = False
        forward = False
        delete = False
        markdown = False
        quote = False
        rss = False
        typing = False
        wait = False


class FinishedSession:
    """
    结束会话。
    """

    def __init__(
        self, session, message_id: Union[List[int], List[str], int, str], result
    ):
        self.session = session
        if isinstance(message_id, (int, str)):
            message_id = [message_id]
        self.message_id = message_id
        self.result = result

    async def delete(self):
        """
        用于删除这条消息。
        """
        raise NotImplementedError

    def __str__(self):
        return f"FinishedSession(message_id={self.message_id}, result={self.result})"


class FetchedSession:
    """
    获取消息会话。
    """

    def __init__(
        self,
        target_from: str,
        target_id: Union[str, int],
        sender_from: Optional[str],
        sender_id: Optional[Union[str, int]],
    ):
        target_id_ = f"{target_from}|{target_id}"
        sender_id_ = None
        if sender_from and sender_id:
            sender_id_ = f"{sender_from}|{sender_id}"
        self.session_info = SessionInfo(
            target_id=target_id_,
            sender_id=sender_id_,
            target_from=target_from,
            sender_from=sender_from,
            sender_name="",
            client_name="",
            message_id=0,
        )
        self.parent = MessageSession(self.session_info)

    async def send_direct_message(
        self,
        message_chain: Union[MessageChain, str, list, MessageElement],
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ):
        """
        用于向获取对象发送消息。

        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链。
        :param disable_secret_check: 是否禁用消息检查。（默认为False）
        :param enable_parse_message: 是否允许解析消息。（此参数作接口兼容用，仅QQ平台使用，默认为True）
        :param enable_split_image: 是否允许拆分图片发送。（此参数作接口兼容用，仅Telegram平台使用，默认为True）
        :return: 被发送的消息链。
        """
        return await self.parent.send_direct_message(
            message_chain,
            disable_secret_check,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )

    sendDirectMessage = send_direct_message


class FetchTarget:
    """
    获取消息会话对象。
    """

    name = ""

    @staticmethod
    async def fetch_target(
        target_id: str, sender_id: Optional[Union[int, str]] = None
    ) -> FetchedSession:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        raise NotImplementedError

    @staticmethod
    async def fetch_target_list(
        target_list: List[Union[int, str]]
    ) -> List[FetchedSession]:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        raise NotImplementedError

    @staticmethod
    async def post_message(
        module_name: str,
        message: str,
        user_list: Optional[List[FetchedSession]] = None,
        i18n: bool = False,
        **kwargs: Dict[str, Any],
    ):
        """
        尝试向开启此模块的对象发送一条消息。

        :param module_name: 模块名称。
        :param message: 消息文本。
        :param user_list: 用户列表。
        :param i18n: 是否使用i18n。若为True则`message`为本地化键名。（或为指定语言的dict映射表（k=语言，v=文本））
        """
        raise NotImplementedError

    @staticmethod
    async def post_global_message(
        message: str,
        user_list: Optional[List[FetchedSession]] = None,
        i18n: bool = False,
        **kwargs,
    ):
        """
        尝试向客户端内的任意对象发送一条消息。

        :param message: 消息文本。
        :param user_list: 用户列表。
        :param i18n: 是否使用i18n，若为True则`message`为本地化键名。（或为指定语言的dict映射表（k=语言，v=文本））
        """
        raise NotImplementedError

    postMessage = post_message
    postGlobalMessage = post_global_message


add_export(MessageSession)


add_export(FetchTarget)
add_export(FetchedSession)
add_export(FinishedSession)


__all__ = ["SessionInfo", MessageSession]
