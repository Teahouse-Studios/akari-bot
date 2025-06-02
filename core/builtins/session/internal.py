from __future__ import annotations

import asyncio
import warnings
from datetime import datetime, UTC as datetimeUTC
from typing import Any, Optional, Union, TYPE_CHECKING, List, Match, Tuple, Coroutine, Dict

from attrs import define

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.builtins.session.info import SessionInfo, FetchedSessionInfo
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.builtins.types import MessageElement
from core.builtins.utils import confirm_command
from core.config import Config
from core.constants import FinishedException, WaitCancelException
from core.exports import add_export, exports
from core.logger import Logger

if TYPE_CHECKING:
    from core.queue.server import JobQueueServer


@define
class MessageSession:
    session_info: SessionInfo
    sent: List[MessageChain] = []
    trigger_msg: Optional[str] = ''
    matched_msg: Optional[Union[Match[str], Tuple[Any]]] = None
    parsed_msg: Optional[dict] = None

    @classmethod
    async def from_session_info(cls, session: SessionInfo):
        return cls(
            session_info=session
        )

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
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        message_chain = MessageChain.assign(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            message_chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))

        return_val = await _queue_server.send_message_signal_to_client(self.session_info, message_chain, quote=quote)

        if callback:
            SessionTaskManager.add_callback(return_val["message_id"], callback)

        return FinishedSession(self.session_info, return_val["message_id"])

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
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        message_chain = MessageChain.assign(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            message_chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))

        await _queue_server.send_message_signal_to_client(self.session_info, message_chain, wait=False)

    def as_display(self, text_only: bool = False) -> str:
        """
        用于将消息转换为一般文本格式。

        :param text_only: 是否只保留纯文本。（默认为False）
        :return: 转换后的字符串。
        """
        return self.session_info.messages.to_str(text_only)

    async def delete(self):
        """
        用于删除这条消息。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.delete_message_signal_to_client(self.session_info, self.session_info.message_id)

    async def check_native_permission(self) -> bool:
        """
        用于检查消息发送者原本在聊天平台中是否具有管理员权限。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        return await _queue_server.check_session_native_permission(self.session_info)

    async def msgchain2nodelist(self, msg_chain_list: List[MessageChain], sender_name: Optional[str] = None,
                                ) -> list[Dict]:
        """
        用于将消息链列表转换为节点列表（QQ）。
        :param msg_chain_list: 消息链列表。
        :param sender_name: 用于指定发送者名称。
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
            message_chain = MessageChain.assign(message_chain)
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
            message_chain = MessageChain.assign(message_chain)
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
        self.session_info.tmp["enforce_send_by_master_client"] = True
        send = None
        ExecutionLockList.remove(self)
        message_chain = MessageChain.assign(message_chain)
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
            message_chain = MessageChain.assign(message_chain)
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
        return bool(self.session_info.sender_info.superuser)

    async def check_permission(self) -> bool:
        """
        用于检查消息发送者在对话内的权限。
        """
        if self.session_info.sender_id in self.session_info.custom_admins or self.session_info.sender_info.superuser:
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
                ftime_template.append(self.session_info.locale.t("time.date.iso.format"))
            else:
                ftime_template.append(self.session_info.locale.t("time.date.format"))
        if time:
            if seconds:
                ftime_template.append(self.session_info.locale.t("time.time.format"))
            else:
                ftime_template.append(self.session_info.locale.t("time.time.nosec.format"))
        if timezone:
            if self.session_info._tz_offset == "+0":
                ftime_template.append("(UTC)")
            else:
                ftime_template.append(f"(UTC{self.session_info._tz_offset})")
        return (
            datetime.fromtimestamp(timestamp, datetimeUTC) + self.session_info.timezone_offset
        ).strftime(" ".join(ftime_template))

    def __hash__(self):
        """
        用于将消息会话对象转换为哈希值。
        """
        return hash(self.session_info.session_id)


@define
class FinishedSession:
    """
    结束会话。
    """
    session: SessionInfo
    message_id: Union[List[int], List[str], int, str] = None

    @classmethod
    def assign(cls, session: SessionInfo, message_id: Union[List[int], List[str], int, str]):
        if isinstance(message_id, (int, str)):
            message_id = [message_id]
        return cls(session, message_id)

    async def delete(self):
        """
        用于删除这条消息。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.delete_message_signal_to_client(self.session, self.message_id)

    def __str__(self):
        return f"FinishedSession(message_id={self.message_id})"


@define
class FetchedMessageSession(MessageSession):
    """
    主动获取的消息会话。
    """
    @classmethod
    async def from_session_info(cls, session: Union[FetchedSessionInfo, SessionInfo]):
        return cls(
            session_info=session
        )


add_export(MessageSession)
add_export(FinishedSession)


__all__ = [SessionInfo, FetchedMessageSession]
