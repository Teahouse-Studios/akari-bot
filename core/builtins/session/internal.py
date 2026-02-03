from __future__ import annotations

import asyncio
from datetime import datetime, UTC as datetimeUTC
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Coroutine, Match, TYPE_CHECKING

from attrs import define
from deprecated import deprecated
from japanera import EraDate

from core.builtins.message.chain import MessageChain, get_message_chain, Chainable
from core.builtins.message.internal import I18NContext
from core.builtins.session.info import SessionInfo, FetchedSessionInfo
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.builtins.types import MessageElement
from core.builtins.utils import confirm_command
from core.config import Config
from core.constants import SessionFinished, WaitCancelException
from core.exports import add_export, exports
from core.utils.func import is_int

if TYPE_CHECKING:
    from core.queue.server import JobQueueServer

quick_confirm = Config("quick_confirm", True)


@define
class MessageSession:
    session_info: SessionInfo
    sent: list[MessageChain] = []
    trigger_msg: str | None = ""
    matched_msg: Match[str] | tuple[Any, ...] | None = None
    parsed_msg: dict | None = None

    @property
    @deprecated(reason="Use `session_info` instead.")
    def target(self) -> SessionInfo:
        return self.session_info

    @classmethod
    async def from_session_info(cls, session: SessionInfo):
        return cls(
            session_info=session
        )

    async def send_message(
        self,
        message_chain: Chainable,
        quote: bool = True,
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
        callback: Any | None = None,
    ) -> FinishedSession:
        """
        用于向消息发送者返回消息。

        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链。
        :param quote: 是否引用传入dict中的消息。（默认为True）
        :param disable_secret_check: 是否禁用消息检查。（默认为False）
        :param enable_parse_message: 是否允许解析消息。
        :param enable_split_image: 是否允许拆分图片发送。（此参数作接口兼容用，仅telegram平台使用，默认为True）
        :param callback: 回调函数，用于在消息发送完成后回复本消息执行的函数。
        :return: 被发送的消息链。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        message_chain = get_message_chain(self.session_info, chain=message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            message_chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))

        return_val = await _queue_server.client_send_message(self.session_info, message_chain,
                                                             quote=quote,
                                                             enable_parse_message=enable_parse_message,
                                                             enable_split_image=enable_split_image)
        if "message_id" in return_val:
            if callback:
                SessionTaskManager.add_callback(return_val["message_id"], callback)

            return FinishedSession(self.session_info, return_val["message_id"])
        return FinishedSession(self.session_info, [])

    async def finish(
        self,
        message_chain: Chainable | None = None,
        quote: bool = True,
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
        callback: Coroutine | None = None,
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
        raise SessionFinished(f)

    async def send_direct_message(
        self,
        message_chain: Chainable,
        disable_secret_check: bool = False,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
        callback: Coroutine | None = None,
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
        message_chain = get_message_chain(session=self.session_info, chain=message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            message_chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))

        return_val = await _queue_server.client_send_message(self.session_info, message_chain, wait=False,
                                                             enable_parse_message=enable_parse_message,
                                                             enable_split_image=enable_split_image)
        if callback:
            SessionTaskManager.add_callback(return_val["message_id"], callback)

    def as_display(
            self,
            text_only: bool = False,
            element_filter: tuple[MessageElement, ...] = None,
            connector: str = " ") -> str:
        """
        用于将消息转换为一般文本格式。

        :param text_only: 是否只保留纯文本。（默认为False）
        :param element_filter: 元素过滤器，用于过滤消息链中的元素。（默认为None）
        :param connector: 元素连接符，用于连接消息链中的各个元素。（默认为" "）
        :return: 转换后的字符串。
        """
        return self.session_info.messages.to_str(text_only, element_filter=element_filter, connector=connector)

    async def delete(self, reason: str | None = None):
        """
        用于删除这条消息。

        :param reason: 原因（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_delete_message(self.session_info, self.session_info.message_id, reason)

    async def restrict_member(self, user_id: str | list[str], duration: int | None = None, reason: str | None = None):
        """
        用于禁言会话内成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID
        :param duration: 禁言时长
        :param reason: 原因（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_restrict_member(self.session_info, user_id, duration, reason)

    async def unrestrict_member(self, user_id: str | list[str]):
        """
        用于解除禁言成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_unrestrict_member(self.session_info, user_id)

    async def kick_member(self, user_id: str | list[str], reason: str | None = None):
        """
        用于踢出成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID
        :param reason: 原因（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_kick_member(self.session_info, user_id, reason)

    async def ban_member(self, user_id: str | list[str], reason: str | None = None):
        """
        用于封禁成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID
        :param reason: 原因（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_ban_member(self.session_info, user_id, reason)

    async def unban_member(self, user_id: str | list[str]):
        """
        用于解除封禁成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_unban_member(self.session_info, user_id)

    async def add_reaction(self, emoji: str) -> Any:
        """
        用于给这条消息添加反应。

        :param emoji: 反应内容（如表情符号）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        return await _queue_server.client_add_reaction(self.session_info, self.session_info.message_id, emoji)

    async def remove_reaction(self, emoji: str) -> Any:
        """
        用于给这条消息删除反应。

        :param emoji: 反应内容（如表情符号）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        return await _queue_server.client_remove_reaction(self.session_info, self.session_info.message_id, emoji)

    async def check_native_permission(self) -> bool:
        """
        用于检查消息发送者原本在聊天平台中是否具有管理员权限。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        return await _queue_server.client_check_native_permission(self.session_info)

    async def handle_error_signal(self):
        """
        用于处理错误信号。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_error_signal(self.session_info)

    async def hold(self):
        """
        用于持久化会话上下文，用于手动控制会话的生命周期，避免会话结束后资源被释放。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_hold_context(self.session_info)

    async def release(self):
        """
        用于手动释放持久化的会话。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_release_context(self.session_info)

    async def start_typing(self):
        """
        用于在会话中开始输入状态。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_start_typing_signal(self.session_info)

    async def end_typing(self):
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_end_typing_signal(self.session_info)

    async def _add_confirm_reaction(self, message_id: str | list[str]):
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        if self.session_info.support_reaction:
            if self.session_info.client_name in ["QQ", "QQBot"]:
                await _queue_server.client_add_reaction(self.session_info, message_id, "11093")
                await _queue_server.client_add_reaction(self.session_info, message_id, "10060")
            else:
                await _queue_server.client_add_reaction(self.session_info, message_id, "⭕")
                await _queue_server.client_add_reaction(self.session_info, message_id, "❌")

    async def wait_confirm(
        self,
        message_chain: Chainable | None = None,
        quote: bool = True,
        delete: bool = True,
        timeout: float | None = 120,
        append_instruction: bool = True,
        no_confirm_action: bool = True
    ) -> bool:
        """
        一次性模板，用于等待触发对象确认。

        :param message_chain: 需要发送的确认消息，可不填。
        :param quote: 是否引用传入dict中的消息。（默认为True）
        :param delete: 是否在触发后删除消息。（默认为True）
        :param timeout: 超时时间。（默认为120）
        :param append_instruction: 是否在发送的消息中附加提示。
        :param no_confirm_action: 在 `no_confirm` 配置项启用后的默认行为。
        :return: 若对象发送confirm_command中的其一文本时返回True，反之则返回False。
        """
        send = None
        ExecutionLockList.remove(self)
        await self.end_typing()
        if Config("no_confirm", False):
            return no_confirm_action
        if message_chain:
            message_chain = get_message_chain(self.session_info, message_chain)
        else:
            message_chain = MessageChain.assign(I18NContext("core.message.confirm"))
        if append_instruction:
            if self.session_info.support_reaction and quick_confirm:
                if self.session_info.client_name == "QQ":
                    message_chain.append(I18NContext("message.wait.confirm.prompt.qq"))
                else:
                    message_chain.append(I18NContext("message.wait.confirm.prompt.reaction"))
            else:
                message_chain.append(I18NContext("message.wait.confirm.prompt"))
        send = await self.send_message(message_chain, quote)
        await asyncio.sleep(0.1)
        if quick_confirm:
            await self._add_confirm_reaction(send.message_id)
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
        message_chain: Chainable | None = None,
        quote: bool = True,
        delete: bool = False,
        timeout: float | None = 120,
        append_instruction: bool = True,
    ) -> MessageSession:
        """
        一次性模板，用于等待对象的下一条消息。

        :param message_chain: 需要发送的确认消息，可不填。
        :param quote: 是否引用传入dict中的消息。（默认为True）
        :param delete: 是否在触发后删除消息。（默认为False）
        :param timeout: 超时时间。（默认为120）
        :param append_instruction: 是否在发送的消息中附加提示。
        :param add_confirm_reaction: 是否在发送的消息上添加确认反应。
        :return: 下一条消息的MessageChain对象。
        """
        send = None
        ExecutionLockList.remove(self)
        await self.end_typing()
        if message_chain:
            message_chain = get_message_chain(self.session_info, message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.wait.next_message.prompt"))
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

    async def wait_anyone(
        self,
        message_chain: Chainable | None = None,
        quote: bool = False,
        delete: bool = False,
        timeout: float | None = 120,
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
        await self.end_typing()
        if message_chain:
            message_chain = get_message_chain(self.session_info, message_chain)
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

    async def wait_reply(
        self,
        message_chain: Chainable,
        quote: bool = True,
        delete: bool = False,
        timeout: float | None = 120,
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
        if not self.session_info.support_quote:
            message_chain = get_message_chain(self.session_info, message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.wait.next_message.prompt"))
            if all_:
                return await self.wait_anyone(message_chain, False, delete, timeout)
            return await self.wait_next_message(message_chain, False, delete, timeout, False)

        send = None
        ExecutionLockList.remove(self)
        await self.end_typing()
        message_chain = get_message_chain(self.session_info, message_chain)
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

    async def call_onebot_api(self, api_name: str, **kwargs) -> Any:
        """
        调用 OneBot API。

        :param api_name: API 名称
        :param kwargs: API 参数
        :return: API 返回结果
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        return await _queue_server.call_onebot_api(self.session_info, api_name=api_name, **kwargs)

    @deprecated(reason="Use `call_onebot_api` instead.")
    async def call_api(self, api_name: str, **kwargs):
        return await self.call_onebot_api(api_name, **kwargs)

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
    callOneBotAPI = call_onebot_api

    def format_time(
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
        dt = datetime.fromtimestamp(timestamp, datetimeUTC) + self.session_info.timezone_offset
        ftime_template = []
        if date:
            if iso:
                ftime_template.append(self.session_info.locale.t("time.date.iso.format"))
            elif self.session_info.locale.locale == "ja_jp":
                era_date = EraDate.from_date(dt).strftime(self.session_info.locale.t("time.date.format"))
                ftime_template.append(era_date)
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

    def format_num(
        self,
        number: Decimal | int | str,
        precision: int = 0
    ) -> str:
        """
        格式化数字。

        :param number: 数字。
        :param precision: 保留小数点位数。
        :returns: 本地化后的数字。
        """

        def _get_cjk_unit(number: Decimal) -> tuple[int, Decimal] | None:
            if number >= Decimal("10e11"):
                return 3, Decimal("10e11")
            if number >= Decimal("10e7"):
                return 2, Decimal("10e7")
            if number >= Decimal("10e3"):
                return 1, Decimal("10e3")
            return None

        def _get_unit(number: Decimal) -> tuple[int, Decimal] | None:
            if number >= Decimal("10e8"):
                return 3, Decimal("10e8")
            if number >= Decimal("10e5"):
                return 2, Decimal("10e5")
            if number >= Decimal("10e2"):
                return 1, Decimal("10e2")
            return None

        def _fmt_num(number: Decimal, precision: int) -> str:
            number = number.quantize(
                Decimal(f"1.{"0" * precision}"), rounding=ROUND_HALF_UP
            )
            num_str = f"{number:.{precision}f}".rstrip("0").rstrip(".")
            return num_str if precision > 0 else str(int(number))

        if is_int(number):
            number = int(number)
        else:
            return str(number)

        if self.session_info.locale.locale in ["ja_jp", "zh_cn", "zh_tw"]:
            unit_info = _get_cjk_unit(Decimal(number))
        else:
            unit_info = _get_unit(Decimal(number))

        if not unit_info:
            return str(number)

        unit, scale = unit_info
        fmted_num = _fmt_num(number / scale, precision)
        return self.session_info.locale.t_str(f"{fmted_num} {{I18N:i18n.unit.{unit}}}", fallback_failed_prompt=True)

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
    message_id: list[int] | list[str] | int | str | None = None

    @classmethod
    def assign(cls, session: SessionInfo, message_id: list[int] | list[str] | int | str):
        if isinstance(message_id, (int, str)):
            message_id = [message_id]
        return cls(session, message_id)

    async def delete(self):
        """
        用于删除这条消息。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_delete_message(self.session, self.message_id)

    def __str__(self):
        return f"FinishedSession(message_id={self.message_id})"


@define
class FetchedMessageSession(MessageSession):
    """
    主动获取的消息会话。
    """

    @classmethod
    async def from_session_info(cls, session: FetchedSessionInfo | SessionInfo):
        return cls(
            session_info=session
        )


add_export(MessageSession)
add_export(FinishedSession)

__all__ = ["SessionInfo", "FetchedMessageSession"]
