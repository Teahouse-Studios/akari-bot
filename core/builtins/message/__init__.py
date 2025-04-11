from __future__ import annotations

import asyncio
from datetime import datetime, UTC as datetimeUTC, timedelta
from re import Match
from typing import Any, Coroutine, Dict, List, Optional, Tuple, Union

from core.builtins.message.chain import *
from core.builtins.message.elements import MessageElement
from core.builtins.message.internal import *
from core.builtins.utils import confirm_command
from core.config import Config
from core.constants.exceptions import WaitCancelException, FinishedException
from core.database.models import SenderInfo, TargetInfo
from core.exports import add_export
from core.i18n import Locale
from core.logger import Logger
from core.types.message import MsgInfo, Session
from core.utils.text import parse_time_string


class ExecutionLockList:
    """
    执行锁。
    """

    _list = set()

    @staticmethod
    def add(msg: MessageSession):
        target_id = msg.target.sender_id
        ExecutionLockList._list.add(target_id)

    @staticmethod
    def remove(msg: MessageSession):
        target_id = msg.target.sender_id
        if target_id in ExecutionLockList._list:
            ExecutionLockList._list.remove(target_id)

    @staticmethod
    def check(msg: MessageSession):
        target_id = msg.target.sender_id
        return target_id in ExecutionLockList._list

    @staticmethod
    def get():
        return ExecutionLockList._list


class MessageTaskManager:
    """
    消息计划管理器。
    """

    _task_list = {}
    _callback_list = {}

    @classmethod
    def add_task(
        cls,
        session: MessageSession,
        flag: asyncio.Event,
        all_: bool = False,
        reply: Optional[Union[List[int], List[str], int, str]] = None,
        timeout: Optional[float] = 120,
    ):
        sender = session.target.sender_id
        task_type = "reply" if reply else "wait"
        if all_:
            sender = "all"

        if session.target.target_id not in cls._task_list:
            cls._task_list[session.target.target_id] = {}
        if sender not in cls._task_list[session.target.target_id]:
            cls._task_list[session.target.target_id][sender] = {}
        cls._task_list[session.target.target_id][sender][session] = {
            "flag": flag,
            "active": True,
            "type": task_type,
            "reply": reply,
            "ts": datetime.now().timestamp(),
            "timeout": timeout,
        }
        Logger.debug(cls._task_list)

    @classmethod
    def add_callback(
        cls,
        message_id: Union[List[int], List[str], int, str],
        callback: Optional[Coroutine],
    ):
        cls._callback_list[message_id] = {
            "callback": callback,
            "ts": datetime.now().timestamp(),
        }

    @classmethod
    def get_result(cls, session: MessageSession):
        if (
            "result"
            in cls._task_list[session.target.target_id][session.target.sender_id][
                session
            ]
        ):
            return cls._task_list[session.target.target_id][session.target.sender_id][
                session
            ]["result"]
        return None

    @classmethod
    def get(cls):
        return cls._task_list

    @classmethod
    async def bg_check(cls):
        for target in cls._task_list:
            for sender in cls._task_list[target]:
                for session in cls._task_list[target][sender]:
                    if cls._task_list[target][sender][session]["active"]:
                        if datetime.now().timestamp() - cls._task_list[target][sender][
                            session
                        ]["ts"] > cls._task_list[target][sender][session].get(
                            "timeout", 3600
                        ):
                            cls._task_list[target][sender][session]["active"] = False
                            cls._task_list[target][sender][session][
                                "flag"
                            ].set()  # no result = cancel
        for message_id in cls._callback_list.copy():
            if datetime.now().timestamp() - cls._callback_list[message_id]["ts"] > 3600:
                del cls._callback_list[message_id]

    @classmethod
    async def check(cls, session: MessageSession):
        if session.target.target_id in cls._task_list:
            senders = []
            if session.target.sender_id in cls._task_list[session.target.target_id]:
                senders.append(session.target.sender_id)
            if "all" in cls._task_list[session.target.target_id]:
                senders.append("all")
            if senders:
                for sender in senders:
                    for s in cls._task_list[session.target.target_id][sender]:
                        get_ = cls._task_list[session.target.target_id][sender][s]
                        if get_["type"] == "wait":
                            get_["result"] = session
                            get_["active"] = False
                            get_["flag"].set()
                        elif get_["type"] == "reply":
                            if isinstance(get_["reply"], list):
                                for reply in get_["reply"]:
                                    if reply == session.target.reply_id:
                                        get_["result"] = session
                                        get_["active"] = False
                                        get_["flag"].set()
                                        break
                            else:
                                if get_["reply"] == session.target.reply_id:
                                    get_["result"] = session
                                    get_["active"] = False
                                    get_["flag"].set()
        if session.target.reply_id in cls._callback_list:
            await cls._callback_list[session.target.reply_id]["callback"](session)


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


class MessageSession:
    """
    消息会话。
    """

    def __init__(self, target: MsgInfo, session: Session):
        self.target = target
        self.session = session
        self.sent: List[MessageChain] = []
        self.trigger_msg: Optional[str] = None
        self.matched_msg: Optional[Union[Match[str], Tuple[Any]]] = None
        self.parsed_msg: Optional[dict] = None
        self.prefixes: List[str] = []
        self.target_info: Optional[TargetInfo] = None
        self.sender_info: Optional[SenderInfo] = None
        self.muted: Optional[bool] = None
        self.sender_data: Optional[dict] = None
        self.target_data: Optional[dict] = None
        self.custom_admins: Optional[list] = None
        self.enabled_modules: Optional[dict] = None
        self.locale: Optional[Locale] = None
        self.name: Optional[str] = None
        self._tz_offset = None
        self.timezone_offset: Optional[timedelta] = None
        self.petal: Optional[int] = None

        self.tmp = {}
        asyncio.create_task(self.data_init())

    async def data_init(self):
        get_sender_info = await SenderInfo.get_by_sender_id(self.target.sender_id)
        get_target_info = await TargetInfo.get_by_target_id(self.target.target_id)
        self.target_info = get_target_info
        self.sender_info = get_sender_info
        self.muted = self.target_info.muted
        self.sender_data = self.sender_info.sender_data
        self.target_data = self.target_info.target_data
        self.petal = self.sender_info.petal
        self.custom_admins = self.target_info.custom_admins
        self.enabled_modules = self.target_info.modules
        self.locale = Locale(self.target_info.locale)
        self.name = self.locale.t("bot_name")
        self._tz_offset = self.target_data.get(
            "timezone_offset", Config("timezone_offset", "+8")
        )
        self.timezone_offset = parse_time_string(self._tz_offset)

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, timeout=timeout)
        try:
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        result = MessageTaskManager.get_result(self)
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
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, timeout=timeout)
        try:
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        result = MessageTaskManager.get_result(self)
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
        flag = asyncio.Event()
        MessageTaskManager.add_task(
            self, flag, reply=send.message_id, all_=all_, timeout=timeout
        )
        try:
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        result = MessageTaskManager.get_result(self)
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
        flag = asyncio.Event()
        MessageTaskManager.add_task(self, flag, all_=True, timeout=timeout)
        try:
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        result = MessageTaskManager.get()[self.target.target_id]["all"][self]
        if "result" in result:
            if send and delete:
                await send.delete()
            return MessageTaskManager.get()[self.target.target_id]["all"][self][
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
        if self.target.sender_id in self.custom_admins or self.sender_info.superuser:
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


class FetchedSession:
    """
    获取消息会话。
    """

    def __init__(
        self,
        target_from: str,
        target_id: Union[str, int],
        sender_from: Optional[str] = None,
        sender_id: Optional[Union[str, int]] = None,
    ):
        if not sender_from:
            sender_from = target_from
        if not sender_id:
            sender_id = target_id
        self.target = MsgInfo(
            target_id=f"{target_from}|{target_id}",
            sender_id=f"{sender_from}|{sender_id}",
            target_from=target_from,
            sender_from=sender_from,
            sender_name="",
            client_name="",
            message_id=0,
        )
        self.session = Session(message=False, target=target_id, sender=sender_id)
        self.parent = MessageSession(self.target, self.session)

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
add_export(ExecutionLockList)
add_export(MessageTaskManager)
add_export(FetchTarget)
add_export(FetchedSession)
add_export(FinishedSession)


__all__ = [
    "MessageSession",
    "ExecutionLockList",
    "MessageTaskManager",
    "FetchTarget",
    "FetchedSession",
    "FinishedSession",
]
