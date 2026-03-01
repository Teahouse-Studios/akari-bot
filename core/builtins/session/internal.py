"""
消息会话内部模块 - 提供消息会话的核心实现和方法。

该模块定义了 MessageSession 和 FetchedMessageSession 类，提供了
发送消息、接收回复、等待用户输入等消息交互的核心功能。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, UTC
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

# 快速确认模式 - 允许用户快速确认操作
quick_confirm = Config("quick_confirm", True)


@define
class MessageSession:
    """
    消息会话类 - 处理与用户的交互。

    该类提供了一套完整的消息交互接口，包括发送消息、接收回复、等待用户输入等功能。
    每个消息会话对应一个用户在某个平台的一条消息。

    属性说明:
        session_info: 会话信息对象，包含会话的所有基本信息
        sent: 已发送消息链列表，用于跟踪消息历史
        trigger_msg: 触发本会话的原始消息文本
        matched_msg: 正则表达式或其他匹配的结果
        parsed_msg: 已解析的消息内容（如命令参数）
    """

    # 会话信息 - 存储会话的所有基本信息
    session_info: SessionInfo

    # 已发送消息列表 - 用于跟踪和管理已发送的消息
    sent: list[MessageChain] = []

    # 触发消息 - 原始的触发消息文本内容
    trigger_msg: str | None = ""

    # 匹配结果 - 正则匹配或其他处理的结果
    matched_msg: Match[str] | tuple[Any, ...] | None = None

    # 解析后的消息 - 命令参数等解析结果
    parsed_msg: dict | None = None

    @property
    @deprecated(reason="Use `session_info` instead.")
    def target(self) -> SessionInfo:
        """
        (已弃用) 获取会话的目标信息。

        使用 session_info 替代此属性。

        :return: 会话信息对象
        """
        return self.session_info

    @classmethod
    async def from_session_info(cls, session: SessionInfo):
        """
        从会话信息创建消息会话实例。

        :param session: 会话信息对象
        :return: 消息会话实例
        """
        return cls(session_info=session)

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

        该方法将消息发送给触发消息的用户，并返回一个 FinishedSession 对象
        用于进一步操作（如删除消息、添加反应等）。

        处理流程：
        1. 将消息链转换为平台特定的格式
        2. 进行安全检查（检查是否包含敏感信息）
        3. 将消息发送到消息队列
        4. 如果有回调函数，注册回调

        :param message_chain: 消息链，若传入 str 则自动创建一条带有 PlainElement 的消息链
        :param quote: 是否引用原始消息（默认为 True）
        :param disable_secret_check: 是否禁用消息安全检查（默认为 False）
        :param enable_parse_message: 是否允许解析消息（此参数作接口兼容用，仅 QQ 平台使用，默认为 True）
        :param enable_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅 Telegram 平台使用，默认为 True）
        :param callback: 回调函数，在消息发送完成后执行（可选）
        :return: FinishedSession 对象，包含消息 ID，可用于后续操作

        :raises SessionFinished: 如果发送过程中抛出异常
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]

        # ========== 步骤 1: 转换消息链格式 ==========
        # 根据平台和会话信息选择合适的消息链格式
        message_chain = get_message_chain(self.session_info, chain=message_chain)

        # ========== 步骤 2: 安全检查 ==========
        # 检查消息是否包含敏感信息（如 API 密钥、密码等）
        if not message_chain.is_safe and not disable_secret_check:
            # 包含敏感信息，替换为安全提示消息
            message_chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))

        # ========== 步骤 3: 发送消息 ==========
        # 通过消息队列发送消息，并阻塞等待返回包含消息 ID 的字典
        return_val = await _queue_server.client_send_message(
            self.session_info,
            message_chain,
            quote=quote,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )

        # ========== 步骤 4: 处理回调 ==========
        if "message_id" in return_val:
            # 消息发送成功，如果有回调函数则注册
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

        该方法是处理消息并终止的最终操作。调用此方法后，会抛出 SessionFinished 异常
        来终止当前会话的处理流程，后续代码不会执行。

        处理流程：
        1. 如果提供了消息链，先发送消息
        2. 抛出 SessionFinished 异常终止会话

        :param message_chain: 消息链，若传入 str 则自动创建一条带有 PlainElement 的消息链，可不填
        :param quote: 是否引用原始消息（默认为 True）
        :param disable_secret_check: 是否禁用消息安全检查（默认为 False）
        :param enable_parse_message: 是否允许解析消息（此参数作接口兼容用，仅 QQ 平台使用，默认为 True）
        :param enable_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅 Telegram 平台使用，默认为 True）
        :param callback: 回调函数，在消息发送完成后执行（可选）

        :raises SessionFinished: 总是抛出此异常来终止会话处理
        """
        f = None
        if message_chain:
            # 发送消息，但不返回，而是用于后续的 SessionFinished 异常
            f = await self.send_message(
                message_chain,
                disable_secret_check=disable_secret_check,
                quote=quote,
                enable_parse_message=enable_parse_message,
                enable_split_image=enable_split_image,
                callback=callback,
            )
        # ========== 终止会话 ==========
        # 抛出 SessionFinished 异常，包含已发送消息的信息
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

        与 send_message 不同，直接发送消息不会等待消息队列的处理结果，
        消息会以后台任务的形式发送。

        处理流程：
        1. 获取消息队列服务
        2. 转换消息链格式
        3. 进行安全检查
        4. 以后台任务（非阻塞）方式发送消息
        5. 注册回调函数（如有）

        :param message_chain: 消息链，若传入 str 则自动创建一条带有 PlainElement 的消息链
        :param disable_secret_check: 是否禁用消息安全检查（默认为 False）
        :param enable_parse_message: 是否允许解析消息（此参数作接口兼容用，仅 QQ 平台使用，默认为 True）
        :param enable_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅 Telegram 平台使用，默认为 True）
        :param callback: 回调函数，在消息发送完成后执行（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]

        # ========== 步骤 1: 转换和检查消息 ==========
        message_chain = get_message_chain(session=self.session_info, chain=message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            message_chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))

        # ========== 步骤 2: 以后台任务方式发送消息 ==========
        # wait=False 表示不等待返回，消息会异步发送
        await _queue_server.client_send_message(
            self.session_info,
            message_chain,
            wait=False,
            enable_parse_message=enable_parse_message,
            enable_split_image=enable_split_image,
        )

    def as_display(
        self, text_only: bool = False, element_filter: tuple[MessageElement, ...] = None, connector: str = "\n"
    ) -> str:
        """
        用于将消息转换为一般文本格式。

        :param text_only: 是否只保留纯文本。（默认为 False）
        :param element_filter: 元素过滤器，用于过滤消息链中的元素。（默认为 None）
        :param connector: 元素之间的连接符。（默认为换行）
        :return: 转换后的字符串。
        """
        return self.session_info.messages.to_str(text_only, element_filter=element_filter, connector=connector)

    async def delete(self, reason: str | None = None):
        """
        用于删除这条消息。

        :param reason: 删除原因（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_delete_message(self.session_info, self.session_info.message_id, reason)

    async def restrict_member(self, user_id: str | list[str], duration: int | None = None, reason: str | None = None):
        """
        用于禁言会话内成员，可能需要该会话的管理员权限。

        该方法可以禁言单个或多个用户，禁言时长以秒为单位。

        :param user_id: 用户 ID 或 ID 列表
        :param duration: 禁言时长（秒），为 None 时表示永久禁言
        :param reason: 禁言原因（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_restrict_member(self.session_info, user_id, duration, reason)

    async def unrestrict_member(self, user_id: str | list[str]):
        """
        用于解除禁言成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_unrestrict_member(self.session_info, user_id)

    async def kick_member(self, user_id: str | list[str], reason: str | None = None):
        """
        用于踢出成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        :param reason: 踢出原因（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_kick_member(self.session_info, user_id, reason)

    async def ban_member(self, user_id: str | list[str], reason: str | None = None):
        """
        用于封禁成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        :param reason: 封禁原因（可选）
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_ban_member(self.session_info, user_id, reason)

    async def unban_member(self, user_id: str | list[str]):
        """
        用于解除封禁成员，可能需要该会话的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_unban_member(self.session_info, user_id)

    async def add_reaction(self, emoji: str) -> Any:
        """
        用于给这条消息添加反应。

        支持的反应格式取决于具体平台。

        :param emoji: 反应内容（如表情符号、Unicode 字符等）
        :return: 平台返回的反应结果
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        return await _queue_server.client_add_reaction(self.session_info, self.session_info.message_id, emoji)

    async def remove_reaction(self, emoji: str) -> Any:
        """
        用于给这条消息删除反应。

        :param emoji: 反应内容（如表情符号、Unicode 字符等）
        :return: 平台返回的删除结果
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        return await _queue_server.client_remove_reaction(self.session_info, self.session_info.message_id, emoji)

    async def check_native_permission(self) -> bool:
        """
        用于检查消息发送者原本在聊天平台中是否具有管理员权限。

        这检查的是原生平台权限（如 QQ 群管理员），而非 AkariBot 的权限。

        :return: 如果用户是平台管理员返回 True，否则返回 False
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        return await _queue_server.client_check_native_permission(self.session_info)

    async def handle_error_signal(self):
        """
        用于处理错误信号。

        通知消息队列服务这条消息的处理过程中出现了错误，
        可以用于更新消息状态或执行错误恢复操作。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_error_signal(self.session_info)

    async def hold(self):
        """
        用于持久化会话上下文，用于手动控制会话的生命周期，避免会话结束后资源被释放。

        在需要保持会话活跃状态以处理异步操作时使用。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_hold_context(self.session_info)

    async def release(self):
        """
        用于手动释放持久化的会话。

        释放之前通过 `hold()` 方法保持的会话，允许系统回收相关资源。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_release_context(self.session_info)

    async def start_typing(self):
        """
        用于在会话中开始输入状态。

        显示“正在输入……”提示给其他用户，表示机器人正在处理消息。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_start_typing_signal(self.session_info)

    async def end_typing(self):
        """
        用于结束会话中的输入状态。

        关闭“正在输入……”提示。
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        await _queue_server.client_end_typing_signal(self.session_info)

    async def _add_confirm_reaction(self, message_id: str | list[str]):
        """
        内部方法：添加确认反应。

        自动为不同平台选择合适的确认反应（勾选和叉号）。

        :param message_id: 消息 ID
        """
        _queue_server: "JobQueueServer" = exports["JobQueueServer"]
        if self.session_info.support_reaction:
            if self.session_info.client_name in ["QQ", "QQBot"]:
                # QQ 平台使用特定的反应 ID
                await _queue_server.client_add_reaction(self.session_info, message_id, "11093")
                await _queue_server.client_add_reaction(self.session_info, message_id, "10060")
            else:
                # 其他平台使用 Unicode 表情
                await _queue_server.client_add_reaction(self.session_info, message_id, "⭕")
                await _queue_server.client_add_reaction(self.session_info, message_id, "❌")

    async def wait_confirm(
        self,
        message_chain: Chainable | None = None,
        quote: bool = True,
        delete: bool = True,
        timeout: float | None = 120,
        append_instruction: bool = True,
        no_confirm_action: bool = True,
    ) -> bool:
        """
        一次性模板，用于等待触发对象确认。

        该方法会发送一条消息并等待用户通过反应或确认指令来确认。
        支持两种确认方式：反应确认（如果平台支持）或文本确认。

        处理流程：
        1. 移除执行锁，结束输入状态
        2. 检查是否启用了无确认模式
        3. 发送确认消息（如提供）
        4. 添加反应按钮（如适用）
        5. 等待用户响应
        6. 返回确认结果

        :param message_chain: 需要发送的确认消息，可不填（默认为通用确认提示）
        :param quote: 是否引用原始消息（默认为 True）
        :param delete: 是否在触发后删除消息（默认为 True）
        :param timeout: 超时时间（秒），默认为 120 秒
        :param append_instruction: 是否在发送的消息中附加提示（默认为 True）
        :param no_confirm_action: 在 `no_confirm` 配置项启用后的默认行为（默认为 True）
        :return: 若对象发送确认指令返回 True，反之返回 False

        :raises WaitCancelException: 如果超时或用户未确认
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

        该方法会发送一条提示消息并等待用户发送下一条消息。

        处理流程：
        1. 移除执行锁，结束输入状态
        2. 发送消息（如提供）
        3. 添加提示指令（如启用）
        4. 等待用户发送消息
        5. 返回用户的消息作为新的 MessageSession

        :param message_chain: 需要发送的提示消息，可不填
        :param quote: 是否引用原始消息（默认为 True）
        :param delete: 是否在触发后删除消息（默认为 False）
        :param timeout: 超时时间（秒），默认为 120 秒
        :param append_instruction: 是否在发送的消息中附加提示（默认为 True）
        :return: 用户下一条消息的 MessageSession 对象

        :raises WaitCancelException: 如果超时或出错
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
        一次性模板，用于等待触发对象所属对话内任意成员的消息。

        该方法会发送一条消息并等待该会话中的任何用户（不仅仅是原始触发者）发送消息。

        :param message_chain: 需要发送的消息，可不填
        :param quote: 是否引用原始消息（默认为 False）
        :param delete: 是否在触发后删除消息（默认为 False）
        :param timeout: 超时时间（秒），默认为 120 秒
        :return: 任意用户发送的消息的 MessageSession 对象

        :raises WaitCancelException: 如果超时或出错
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
            return SessionTaskManager.get()[self.session_info.target_id]["all"][self]["result"]
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

        该方法会发送一条消息并等待用户以回复的形式响应（需要平台支持）。

        如果平台不支持回复功能，会退化为 `wait_next_message` 或 `wait_anyone`。

        处理流程：
        1. 检查平台是否支持回复功能
        2. 发送消息
        3. 添加回复提示
        4. 等待用户回复
        5. 返回用户的回复消息

        :param message_chain: 需要发送的消息
        :param quote: 是否引用原始消息（默认为 True）
        :param delete: 是否在触发后删除消息（默认为 False）
        :param timeout: 超时时间（秒），默认为 120 秒
        :param all_: 是否等待任意用户的回复（默认为 False，仅等待触发者）
        :param append_instruction: 是否在发送的消息中附加提示（默认为 True）
        :return: 用户回复消息的 MessageSession 对象

        :raises WaitCancelException: 如果超时或出错
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
        SessionTaskManager.add_task(self, flag, reply=send.message_id, all_=all_, timeout=timeout)
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
        """
        用于暂停执行指定的秒数。

        :param s: 暂停时长（秒）
        """
        ExecutionLockList.remove(self)
        await asyncio.sleep(s)

    def check_super_user(self) -> bool:
        """
        用于检查消息发送者是否为超级用户。

        :return: 如果用户是超级用户返回 True，否则返回 False
        """
        return bool(self.session_info.sender_info.superuser)

    async def check_permission(self) -> bool:
        """
        用于检查消息发送者在对话内的权限。

        检查用户是否拥有管理员权限（包括自定义管理员和平台原生管理员）。

        :return: 如果用户拥有管理员权限返回 True，否则返回 False
        """
        if self.session_info.sender_id in self.session_info.custom_admins or self.session_info.sender_info.superuser:
            return True
        return await self.check_native_permission()

    async def call_onebot_api(self, api_name: str, **kwargs) -> Any:
        """
        调用 OneBot API。

        该方法允许直接调用底层的 OneBot 兼容 API，用于在 QQ 平台进行更高级的操作。

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

        根据会话的地区设置和时区进行本地化格式化。支持多种日期和时间格式。

        :param timestamp: UTC 时间戳
        :param date: 是否显示日期（默认为 True）
        :param iso: 是否以 ISO 格式显示日期（默认为 False）
        :param time: 是否显示时间（默认为 True）
        :param seconds: 是否显示秒（默认为 True）
        :param timezone: 是否显示时区（默认为 True）
        :return: 格式化后的时间字符串

        示例：
        ```
            > session.format_time(1234567890, date=True, time=True)
            'February 13, 2009 23:31:30 (UTC)'
        ```
        """
        dt = datetime.fromtimestamp(timestamp, UTC) + self.session_info.timezone_offset
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
        return (datetime.fromtimestamp(timestamp, UTC) + self.session_info.timezone_offset).strftime(
            " ".join(ftime_template)
        )

    def format_num(self, number: Decimal | int | str, precision: int = 0) -> str:
        """
        格式化数字为本地化的表示。

        根据地区设置进行本地化处理，包括数字分隔符和单位符号的翻译。
        支持自动缩放大数字（如 100万 -> 1百万 或 1M）。

        :param number: 要格式化的数字
        :param precision: 保留小数点位数（默认为 0）
        :return: 本地化格式的数字字符串

        示例：
        ```
            > session.format_num(1000000, precision=1)  # 中文: '100.0万'
            > session.format_num(1000000, precision=1)  # 英文: '1.0M'
        ```
        """

        def _get_cjk_unit(number: Decimal) -> tuple[int, Decimal] | None:
            # 中日韩文字数单位：万（10^4）百万（10^7）兆（10^11）
            if number >= Decimal("10e11"):
                return 3, Decimal("10e11")
            if number >= Decimal("10e7"):
                return 2, Decimal("10e7")
            if number >= Decimal("10e3"):
                return 1, Decimal("10e3")
            return None

        def _get_unit(number: Decimal) -> tuple[int, Decimal] | None:
            # 英文单位：K（10^3）M（10^6）G（10^9）
            if number >= Decimal("10e8"):
                return 3, Decimal("10e8")
            if number >= Decimal("10e5"):
                return 2, Decimal("10e5")
            if number >= Decimal("10e2"):
                return 1, Decimal("10e2")
            return None

        def _fmt_num(number: Decimal, precision: int) -> str:
            # 四舍五入并格式化为指定精度
            number = number.quantize(Decimal(f"1.{'0' * precision}"), rounding=ROUND_HALF_UP)
            num_str = f"{number:.{precision}f}".rstrip("0").rstrip(".")
            return num_str if precision > 0 else str(int(number))

        if is_int(number):
            number = int(number)
        else:
            return str(number)

        # 根据地区选择合适的单位系统
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
        return hash(self.session_info.session_id)

    def __eq__(self, other):
        """
        比较两个消息会话对象是否相等。

        两个会话仅当会话 ID 相同时才认为相等。

        :param other: 另一个对象
        :return: 如果相等返回 True，否则返回 False
        """
        if isinstance(other, MessageSession):
            return self.session_info.session_id == other.session_info.session_id
        return False


@define
class FinishedSession:
    """
    结束会话类 - 表示已完成的消息发送会话。

    该类封装了消息发送后的结果，包含发送到的会话和消息 ID。
    可用于进一步的操作，如删除消息、添加反应等。

    属性说明：
        session: 消息被发送的会话信息
        message_id: 发送的消息 ID（可能是列表，表示多条消息）
    """

    session: SessionInfo
    message_id: list[int] | list[str] | int | str | None = None

    @classmethod
    def assign(cls, session: SessionInfo, message_id: list[int] | list[str] | int | str):
        """
        创建 FinishedSession 实例。

        :param session: 消息会话信息
        :param message_id: 消息 ID，如果是单个值会被转换为列表
        :return: FinishedSession 实例
        """
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
        """返回字符串表示"""
        return f"FinishedSession(message_id={self.message_id})"


@define
class FetchedMessageSession(MessageSession):
    """
    主动获取的消息会话。

    该类用于表示机器人主动获取的消息会话（如通过 API 查询历史消息）。
    继承自 MessageSession，提供相同的消息处理功能。

    示例：
        > session = await FetchedMessageSession.from_session_info(session_info)
    """

    @classmethod
    async def from_session_info(cls, session: FetchedSessionInfo | SessionInfo):
        """
        从会话信息创建主动获取的消息会话实例。

        :param session: 会话信息对象（可以是普通 SessionInfo 或 FetchedSessionInfo）
        :return: FetchedMessageSession 实例
        """
        return cls(session_info=session)


add_export(MessageSession)
add_export(FinishedSession)

__all__ = ["SessionInfo", "FetchedMessageSession"]
