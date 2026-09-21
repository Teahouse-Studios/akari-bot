"""消息会话内部模块 - 提供消息会话的核心实现和方法。"""

from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Coroutine, Match, NoReturn, cast

from akari_bot_i18n.i18n import Locale, safe_strftime
from attrs import define, field
from deprecated import deprecated

from core.builtins.filter import filter_badwords
from core.builtins.message.chain import MessageChain, get_message_chain, Chainable, MessageNodes
from core.builtins.message.internal import Button, ButtonFrame, I18NContext, PlainElement
from core.builtins.session.info import SessionInfo, FetchedSessionInfo
from core.builtins.session.bot_state import BotState
from core.builtins.session.lock import ExecutionLockList, ExecutionState
from core.builtins.session.tasks import SessionTaskManager
from core.builtins.types import MessageElement
from core.builtins.utils import confirm_command
from core.config.base import BaseConfig, CoreConfig
from core.constants import SessionContextUnavailable, SessionFinished, WaitCancelException
from core.exports import add_export
from core.logger import Logger
from core.utils.button import bind_callback_reply_ids, build_button_rows, public_button_reply_ids
from core.utils.func import is_int
from core.utils.media import compress_media_chain
from core.utils.random import Random

from core.queue.contracts import PlatformAPI
from core.queue.errors import RpcRemoteError

# 会话相关配置在导入期取一次快照，避免每次取文案都去读配置
default_locale = BaseConfig.default_locale
quick_confirm = CoreConfig.quick_confirm


def _is_confirmation_message(msg: MessageSession) -> bool:
    value = msg.as_display(text_only=True).strip()
    return value in confirm_command


def confirm_prompt_key(session_info: SessionInfo) -> str:
    """取确认提示的文案键，按会话实际具备的快速确认途径选择。

    :param session_info: 会话信息。
    :return: 提示文案的多语言键。
    """
    if session_info.support_button:
        return "message.wait.confirm.prompt.button"
    if session_info.support_reaction and quick_confirm:
        if session_info.client_name == "QQ":
            return "message.wait.confirm.prompt.qq"
        return "message.wait.confirm.prompt.reaction"
    return "message.wait.confirm.prompt"


def _filter_message_chain_badwords(
    chain: MessageChain | MessageNodes, session_info: SessionInfo
) -> MessageChain | MessageNodes:
    if isinstance(chain, MessageNodes):
        chain.values = [cast(MessageChain, _filter_message_chain_badwords(node, session_info)) for node in chain.values]
        return chain

    for element in chain.values:
        if isinstance(element, PlainElement):
            element.text = session_info.locale.t_str(filter_badwords(element.text))
    return chain


async def normalize_outgoing_chain(session_info: SessionInfo, chain: Any, disable_secret_check: bool):
    """对 hook 改写后的最终出站链完整执行发送规范化。"""
    if not isinstance(chain, (MessageChain, MessageNodes)):
        chain = get_message_chain(session_info, chain=chain)
    chain = _filter_message_chain_badwords(chain, session_info)
    if isinstance(chain, MessageNodes) and not session_info.support_handle_message_nodes:
        from core.utils.image import msgnode2image

        chain = MessageChain.assign(await msgnode2image(chain, session=session_info))
    if isinstance(chain, MessageChain):
        chain = await compress_media_chain(chain)
        if chain is None:
            return None
    if not chain.is_safe and not disable_secret_check:
        chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))
    return chain


@define
class MessageSession:
    """消息会话类 - 处理与用户的交互。"""

    session_info: SessionInfo

    sent: list[MessageChain] = field(factory=list)

    trigger_msg: str = ""

    matched_msg: Match[str] | tuple[Any, ...] | None = None

    parsed_msg: dict = field(factory=dict)

    # 别名改写前用户实际输入的命令首词。模块别名可能把白名单命令并入其它模块
    # （如 merge 现为 bind 的别名），退役策略解析后仍需据此判断放行与否。
    command_original_word: str = field(default="", repr=False, eq=False)

    # 仅存在于 Server 进程中的命令执行状态。通过 wait_* 取得的回复会话会共享
    # 同一个对象，使嵌套等待可以释放／重获同一 lease，并由原始 parser 统一
    # 释放等待结果所持有的平台 context。
    _execution_state: ExecutionState = field(factory=ExecutionState, repr=False, eq=False)
    _execution_state_owner: bool = field(default=True, repr=False, eq=False)

    def _share_execution_state(self, result: "MessageSession") -> None:
        result._execution_state = ExecutionLockList.state(self)
        result._execution_state_owner = False

    def _adopt_wait_result(self, result: "MessageSession") -> None:
        self._share_execution_state(result)
        ExecutionLockList.state(self).held_contexts.append(result)

    async def release_execution_resources(self) -> None:
        """由原始 parser 在命令结束时释放全部等待结果 context。"""
        if not getattr(self, "_execution_state_owner", True):
            return
        state = ExecutionLockList.state(self)
        held_contexts = list(state.held_contexts)
        state.held_contexts.clear()
        if not held_contexts:
            return
        pending = held_contexts
        failures: list[tuple[MessageSession, BaseException]] = []
        # release_context 是跨进程动作；一次瞬时 Queue／平台异常不应把已经
        # hold 的 context 永久遗留。成功项只释放一次，失败项让出一拍后重试。
        for attempt in range(2):
            results = await asyncio.gather(*(result.release() for result in pending), return_exceptions=True)
            failures = [
                (result, error)
                for result, error in zip(pending, results, strict=True)
                if isinstance(error, BaseException)
            ]
            if not failures:
                return
            pending = [result for result, _error in failures]
            if attempt == 0:
                await asyncio.sleep(0)
        for _result, error in failures:
            Logger.error(f"Failed to release a wait-result context after retry: {error!r}")

    @property
    @deprecated(reason="Use `session_info` instead.")
    def target(self) -> SessionInfo:
        """(已弃用) 获取会话信息。

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

    @property
    def t(self):
        if self.session_info:
            return self.session_info.locale.t
        Logger.warning("SessionInfo is not available, returning default language for translation function.")
        return Locale(default_locale).t

    @property
    def t_str(self):
        if self.session_info:
            return self.session_info.locale.t_str
        Logger.warning("SessionInfo is not available, returning default language for translation function.")
        return Locale(default_locale).t_str

    async def send_message(
        self,
        message_chain: Chainable,
        quote: bool = True,
        disable_secret_check: bool = False,
        callback: Any | None = None,
        callback_id: str | None = None,
        callback_timeout: float | None = SessionTaskManager.CALLBACK_TTL,
        callback_once: bool = False,
    ) -> FinishedSession:
        """用于向消息用户返回消息。

        :param message_chain: 消息链，若传入 str 则自动创建一条带有 PlainElement 的消息链
        :param quote: 是否引用原始消息（默认为 True）
        :param disable_secret_check: 是否禁用消息安全检查（默认为 False）
        :param callback: 回调函数，在消息发送完成后执行（可选）
        :param callback_id: 按钮交互使用的虚拟回复 ID；通常由框架自动生成（可选）
        :param callback_timeout: callback 有效秒数；默认为 30 分钟，None 表示不自动过期
        :param callback_once: 是否在首次触发后立即失效；默认为 False
        :return: FinishedSession 对象，包含消息 ID，可用于后续操作

        :raises SessionFinished: 如果发送过程中抛出异常
        """

        chain = get_message_chain(self.session_info, chain=message_chain)
        chain = _filter_message_chain_badwords(chain, self.session_info)

        if isinstance(chain, MessageNodes) and not self.session_info.support_handle_message_nodes:
            from core.utils.image import msgnode2image

            chain = MessageChain.assign(await msgnode2image(chain, session=self.session_info))

        if isinstance(chain, MessageChain):
            chain = await compress_media_chain(chain)
            if chain is None:
                return cast(FinishedSession, None)

        if not chain.is_safe and not disable_secret_check:
            chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))

        # 在 callback 登记之前，避免取消时遗留 pending 注册
        from core.builtins.parser.hooks import (
            OutgoingPayload,
            Stop,
            dispatch_outgoing_before_send,
            dispatch_outgoing_result,
        )

        outgoing_payload = OutgoingPayload(chain=chain, quote=quote)
        stop_send = await dispatch_outgoing_before_send(self, outgoing_payload)
        if isinstance(stop_send, Stop):
            return cast(FinishedSession, FinishedSession(self.session_info, []))
        chain = outgoing_payload.chain
        quote = outgoing_payload.quote

        # 改写后的最终消息必须重新过完整发送规范化（含 MessageNodes 节点校验与平台转换）
        chain = await normalize_outgoing_chain(self.session_info, chain, disable_secret_check)
        if chain is None:
            return cast(FinishedSession, None)
        outgoing_payload.chain = chain

        callback_reply_ids = bind_callback_reply_ids(chain, callback_id) if callback else []

        # 在平台发送前为每次 callback 建立独立注册。
        callback_handle = None
        if callback:
            callback_handle = SessionTaskManager.add_callback(
                self,
                list(callback_reply_ids),
                callback,
                fallback_ids=self.session_info.bot_id,
                timeout=callback_timeout,
                once=callback_once,
                allow_all_reply_ids=public_button_reply_ids(chain),
            )

        try:
            return_val = await PlatformAPI.send_message(
                self.session_info,
                chain,
                quote=quote,
            )
        except (asyncio.CancelledError, SystemExit, KeyboardInterrupt):
            SessionTaskManager.remove_callback(callback_handle)
            raise
        except BaseException:
            SessionTaskManager.remove_callback(callback_handle)
            await dispatch_outgoing_result(self, outgoing_payload, ok=False)
            raise

        if return_val:
            if callback:
                message_ids = return_val
                if isinstance(message_ids, (str, int)):
                    message_ids = [message_ids]
                callback_targets = [str(message_id) for message_id in message_ids]

                if callback_targets:
                    if callback_handle is not None:
                        # callback 可能已在发送回包前被主动撤销、过期或作为一次性
                        # callback 消费；此时 extend 返回 None，不能重新注册。
                        callback_handle = SessionTaskManager.extend_callback(callback_handle, callback_targets)
                    else:
                        callback_targets.extend(
                            reply_id for reply_id in callback_reply_ids if reply_id not in callback_targets
                        )
                        callback_handle = SessionTaskManager.add_callback(
                            self,
                            callback_targets,
                            callback,
                            fallback_ids=self.session_info.bot_id,
                            timeout=callback_timeout,
                            once=callback_once,
                            allow_all_reply_ids=public_button_reply_ids(chain),
                        )
                else:
                    # 空 ID 表示平台发送失败，不能只凭 bot_id 为不存在的消息留下 callback。
                    SessionTaskManager.remove_callback(callback_handle)

            # 观察快照带真实消息 ID 与最终发送内容；慢观察者不会延长 callback 未绑定窗口
            await dispatch_outgoing_result(self, outgoing_payload, ok=True, message_ids=return_val)
            return FinishedSession(self.session_info, return_val)
        SessionTaskManager.remove_callback(callback_handle)
        await dispatch_outgoing_result(self, outgoing_payload, ok=False, message_ids=[])
        return FinishedSession(self.session_info, [])

    async def finish(
        self,
        message_chain: Chainable | None = None,
        quote: bool = True,
        disable_secret_check: bool = False,
        callback: Coroutine | None = None,
        callback_id: str | None = None,
        callback_timeout: float | None = SessionTaskManager.CALLBACK_TTL,
        callback_once: bool = False,
    ) -> NoReturn:
        """用于向消息用户返回消息并终结会话（模块后续代码不再执行）。

        :param message_chain: 消息链，若传入 str 则自动创建一条带有 PlainElement 的消息链，可不填
        :param quote: 是否引用原始消息（默认为 True）
        :param disable_secret_check: 是否禁用消息安全检查（默认为 False）
        :param callback: 回调函数，在消息发送完成后执行（可选）
        :param callback_id: 按钮交互使用的虚拟回复 ID；通常由框架自动生成（可选）
        :param callback_timeout: callback 有效秒数；默认为 30 分钟，None 表示不自动过期
        :param callback_once: 是否在首次触发后立即失效；默认为 False
        :raises SessionFinished: 总是抛出此异常来终止会话处理
        """
        f = None
        if message_chain:
            f = await self.send_message(
                message_chain,
                disable_secret_check=disable_secret_check,
                quote=quote,
                callback=callback,
                callback_id=callback_id,
                callback_timeout=callback_timeout,
                callback_once=callback_once,
            )
        raise SessionFinished(f)

    async def send_direct_message(
        self,
        message_chain: Chainable,
        disable_secret_check: bool = False,
    ):
        """用于向消息用户直接发送消息。

        :param message_chain: 消息链，若传入 str 则自动创建一条带有 PlainElement 的消息链
        :param disable_secret_check: 是否禁用消息安全检查（默认为 False）
        """

        chain = get_message_chain(session=self.session_info, chain=message_chain)
        chain = _filter_message_chain_badwords(chain, self.session_info)
        if isinstance(chain, MessageNodes):
            from core.utils.image import msgnode2image

            chain = MessageChain.assign(await msgnode2image(chain, session=self.session_info))
        if not chain.is_safe and not disable_secret_check:
            chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))
        chain = await compress_media_chain(chain)
        if chain is None:
            return None

        from core.builtins.parser.hooks import (
            OutgoingPayload,
            Stop,
            dispatch_outgoing_before_send,
            dispatch_outgoing_result,
        )

        outgoing_payload = OutgoingPayload(chain=chain)
        stop_send = await dispatch_outgoing_before_send(self, outgoing_payload)
        if isinstance(stop_send, Stop):
            return None
        chain = outgoing_payload.chain
        chain = await normalize_outgoing_chain(self.session_info, chain, disable_secret_check)
        if chain is None:
            return None
        outgoing_payload.chain = chain

        try:
            await PlatformAPI.send_message.submit(self.session_info, chain, quote=outgoing_payload.quote)
        except (asyncio.CancelledError, SystemExit, KeyboardInterrupt):
            raise
        except BaseException:
            await dispatch_outgoing_result(self, outgoing_payload, ok=False)
            raise
        # submit 仅代表接受投递，不能据此发布 sent

    async def send_private_message(
        self,
        message_chain: Chainable,
        user_id: str | None = None,
        disable_secret_check: bool = False,
    ) -> list[str]:
        """用于向指定用户单独发送私聊消息。

        :param message_chain: 消息链，若传入 str 则自动创建一条带有 PlainElement 的消息链
        :param user_id: 目标用户 ID（带平台前缀），留空则发给触发本会话的用户
        :param disable_secret_check: 是否禁用消息安全检查（默认为 False）
        :return: 消息 ID 列表，为空表示发送失败（如平台不支持私信、对方未与机器人建立私聊等）
        """
        user_id = user_id or self.session_info.sender_id
        if not user_id:
            return []

        # 平台不支持私信时无需经过队列，直接判定失败
        if not self.session_info.support_private_msg:
            return []

        chain = get_message_chain(self.session_info, chain=message_chain)
        chain = _filter_message_chain_badwords(chain, self.session_info)
        if isinstance(chain, MessageNodes):
            from core.utils.image import msgnode2image

            chain = MessageChain.assign(await msgnode2image(chain, session=self.session_info))
        if not chain.is_safe and not disable_secret_check:
            chain = MessageChain.assign(I18NContext("error.message.chain.unsafe"))

        chain = await compress_media_chain(chain)
        if chain is None:
            return []

        from core.builtins.parser.hooks import (
            OutgoingPayload,
            Stop,
            dispatch_outgoing_before_send,
            dispatch_outgoing_result,
        )

        outgoing_payload = OutgoingPayload(chain=chain, quote=False)
        stop_send = await dispatch_outgoing_before_send(self, outgoing_payload)
        if isinstance(stop_send, Stop):
            return []
        chain = outgoing_payload.chain
        chain = await normalize_outgoing_chain(self.session_info, chain, disable_secret_check)
        if chain is None:
            return []
        outgoing_payload.chain = chain
        # 私信接口没有引用参数，观察内容始终反映实际的不引用发送。
        outgoing_payload.quote = False

        try:
            return_val = await PlatformAPI.send_private_msg(
                self.session_info,
                user_id,
                chain,
            )
        except (asyncio.CancelledError, SystemExit, KeyboardInterrupt):
            raise
        except BaseException:
            await dispatch_outgoing_result(self, outgoing_payload, ok=False)
            raise
        # 观察入口拿快照，不能改写正式返回值
        await dispatch_outgoing_result(self, outgoing_payload, ok=bool(return_val), message_ids=return_val or [])
        return return_val

    def as_display(
        self, text_only: bool = False, element_filter: tuple[MessageElement, ...] | None = None, connector: str = "\n"
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
        await PlatformAPI.delete_message.submit(self.session_info, self.session_info.message_id, reason)

    async def restrict_member(
        self,
        user_id: str | list[str],
        duration: int | None = None,
        reason: str | None = None,
        wait: bool = False,
    ):
        """用于禁言场景内成员，可能需要该场景的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        :param duration: 禁言时长（秒），为 None 时表示永久禁言
        :param reason: 禁言原因（可选）
        """
        operation = PlatformAPI.restrict_member if wait else PlatformAPI.restrict_member.submit
        return await operation(self.session_info, user_id, duration, reason)

    async def unrestrict_member(self, user_id: str | list[str], wait: bool = False):
        """
        用于解除禁言成员，可能需要该场景的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        """
        operation = PlatformAPI.unrestrict_member if wait else PlatformAPI.unrestrict_member.submit
        return await operation(self.session_info, user_id)

    async def kick_member(self, user_id: str | list[str], reason: str | None = None):
        """
        用于踢出成员，可能需要该场景的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        :param reason: 踢出原因（可选）
        """
        await PlatformAPI.kick_member.submit(self.session_info, user_id, reason)

    async def ban_member(self, user_id: str | list[str], reason: str | None = None):
        """
        用于封禁成员，可能需要该场景的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        :param reason: 封禁原因（可选）
        """
        await PlatformAPI.ban_member.submit(self.session_info, user_id, reason)

    async def unban_member(self, user_id: str | list[str]):
        """
        用于解除封禁成员，可能需要该场景的管理员权限。

        :param user_id: 用户 ID 或 ID 列表
        """
        await PlatformAPI.unban_member.submit(self.session_info, user_id)

    async def grant_permission_group(
        self,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
        wait: bool = False,
    ):
        """为场景成员授予平台原生权限组或角色。"""
        operation = PlatformAPI.grant_permission_group if wait else PlatformAPI.grant_permission_group.submit
        return await operation(
            self.session_info,
            user_id,
            permission_group_id,
            reason,
        )

    async def revoke_permission_group(
        self,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
        wait: bool = False,
    ):
        """移除场景成员的平台原生权限组或角色。"""
        operation = PlatformAPI.revoke_permission_group if wait else PlatformAPI.revoke_permission_group.submit
        return await operation(
            self.session_info,
            user_id,
            permission_group_id,
            reason,
        )

    async def add_reaction(self, emoji: str) -> Any:
        """用于给这条消息添加反应。

        :param emoji: 反应内容（如表情符号、Unicode 字符等）
        :return: 平台返回的反应结果
        """
        return await PlatformAPI.add_reaction(self.session_info, self.session_info.message_id, emoji)

    async def remove_reaction(self, emoji: str) -> Any:
        """
        用于给这条消息删除反应。

        :param emoji: 反应内容（如表情符号、Unicode 字符等）
        :return: 平台返回的删除结果
        """
        return await PlatformAPI.remove_reaction(self.session_info, self.session_info.message_id, emoji)

    async def check_native_permission(self) -> bool:
        """用于检查消息用户原本在聊天平台中是否具有管理员权限。

        :return: 如果用户是平台管理员返回 True，否则返回 False
        """
        return await PlatformAPI.check_native_permission(self.session_info)

    async def check_bot_state(self) -> BotState:
        """Return the bot's context membership and native permission state."""
        return await PlatformAPI.check_bot_state(self.session_info)

    async def handle_error_signal(self):
        """用于处理错误信号。"""
        await PlatformAPI.error_signal.submit(self.session_info)

    async def hold(self):
        """用于持久化会话上下文，用于手动控制会话的生命周期，避免会话结束后资源被释放。"""
        try:
            await PlatformAPI.hold_context(self.session_info)
        except RpcRemoteError as exc:
            if exc.remote_type == SessionContextUnavailable.__name__ or (
                exc.remote_type == ValueError.__name__ and str(exc) == "Session not found in context"
            ):
                raise SessionContextUnavailable(str(exc)) from exc
            raise

    async def release(self):
        """用于手动释放持久化的会话。"""
        await PlatformAPI.release_context(self.session_info)

    async def start_typing(self):
        """用于在会话中开始输入状态。"""
        await PlatformAPI.start_typing(self.session_info)

    async def end_typing(self):
        """用于结束会话中的输入状态。"""
        await PlatformAPI.end_typing(self.session_info)

    async def _add_confirm_reaction(self, message_id: str | list[str]):
        if self.session_info.support_reaction:
            if self.session_info.client_name in ["QQ", "QQBot"]:
                await PlatformAPI.add_reaction(self.session_info, message_id, "11093")
                await PlatformAPI.add_reaction(self.session_info, message_id, "10060")
            else:
                await PlatformAPI.add_reaction(self.session_info, message_id, "⭕")
                await PlatformAPI.add_reaction(self.session_info, message_id, "❌")

    async def wait_confirm(
        self,
        message_chain: Chainable | None = None,
        quote: bool = True,
        delete: bool = True,
        timeout: float | None = 120,
        append_instruction: bool = True,
        no_confirm_action: bool = True,
        release_execution_lock: bool = True,
        consume_any_message: bool = False,
    ) -> bool:
        """一次性模板，用于等待触发对象确认。

        :param message_chain: 需要发送的确认消息，可不填（默认为通用确认提示）
        :param quote: 是否引用原始消息（默认为 True）
        :param delete: 是否在触发后删除消息（默认为 True）
        :param timeout: 超时时间（秒），默认为 120 秒
        :param append_instruction: 是否在发送的消息中附加提示（默认为 True）
        :param no_confirm_action: 在 `no_confirm` 配置项启用后的默认行为（默认为 True）
        :param release_execution_lock: 等待期间是否释放执行锁。Union 合并在建立
                                       双方 barrier 后须保持锁，避免冲突选择期间重新并发。
        :param consume_any_message: 是否将下一条任意消息作为否定结果消费，而不是仅消费确认词。
        :return: 若对象发送确认指令返回 True，反之返回 False

        :raises WaitCancelException: 如果超时或用户未确认
        """
        if CoreConfig.no_confirm:
            return no_confirm_action
        released_lease = ExecutionLockList.remove(self) if release_execution_lock else False
        await self.end_typing()
        if message_chain:
            chain = get_message_chain(self.session_info, message_chain)
        else:
            chain = MessageChain.assign(I18NContext("core.message.confirm"))
        # 合并转发消息无从追加提示行，此时略过
        if append_instruction and isinstance(chain, MessageChain):
            chain.append(I18NContext(confirm_prompt_key(self.session_info)))
        if self.session_info.support_button and isinstance(chain, MessageChain):
            chain.append(Button(self.session_info.locale.t("message.button.yes"), "confirm_yes"))
            chain.append(Button(self.session_info.locale.t("message.button.no"), "confirm_no"))
        send = None
        flag = asyncio.Event()
        SessionTaskManager.add_task(
            self,
            flag,
            timeout=timeout,
            task_type="wait",
            matcher=None if consume_any_message else _is_confirmation_message,
        )
        task_info = None
        try:
            # 等待任务须在跨进程发送提示前登记；平台可能已展示消息并收到用户操作，
            # 而发送 action 的结果尚未回到 Server。
            send = await self.send_message(chain, quote)
            # 添加表情反应需要跨进程网络往返；等待任务必须先登记，否则用户在此期间
            # 发送文本确认或点击按钮会被当作普通消息处理并永久丢失。
            if quick_confirm:
                await self._add_confirm_reaction(send.message_id)
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        finally:
            task_info = SessionTaskManager.remove_task(self)
        result = task_info.get("result") if task_info else None
        if result:
            if send and delete:
                await send.delete()
            confirmed = result.as_display(text_only=True) in confirm_command
            if released_lease and not await ExecutionLockList.acquire(self, wait=True):
                raise WaitCancelException
            return confirmed
        raise WaitCancelException

    async def wait_next_message(
        self,
        message_chain: Chainable | None = None,
        quote: bool = True,
        delete: bool = False,
        timeout: float | None = 120,
        append_instruction: bool = True,
        possibly_choices: list[dict[str, str]] | None = None,
    ) -> MessageSession:
        """一次性模板，用于等待对象的下一条消息。

        :param message_chain: 需要发送的提示消息，可不填
        :param quote: 是否引用原始消息（默认为 True）
        :param delete: 是否在触发后删除消息（默认为 False）
        :param timeout: 超时时间（秒），默认为 120 秒
        :param append_instruction: 是否在发送的消息中附加提示（默认为 True）
        :param possibly_choices: 可能的选项，用于可能的扩展按钮提示。
        :return: 用户下一条消息的 MessageSession 对象

        :raises WaitCancelException: 如果超时或出错
        """
        send = None
        released_lease = ExecutionLockList.remove(self)
        await self.end_typing()
        flag = asyncio.Event()
        SessionTaskManager.add_task(self, flag, timeout=timeout, task_type="wait_next", allow_fallthrough=True)
        task_info = None
        try:
            if message_chain:
                chain = get_message_chain(self.session_info, message_chain)
                # 合并转发消息无从追加提示行，此时略过
                if append_instruction and isinstance(chain, MessageChain):
                    chain.append(I18NContext("message.wait.next_message.prompt"))
                if possibly_choices and self.session_info.support_button and isinstance(chain, MessageChain):
                    chain.append(ButtonFrame(build_button_rows(possibly_choices)))
                send = await self.send_message(chain, quote)
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        finally:
            task_info = SessionTaskManager.remove_task(self)
        result = task_info.get("result") if task_info else None
        if send and delete:
            await send.delete()
        if result:
            if released_lease and not await ExecutionLockList.acquire(self, wait=True):
                raise WaitCancelException
            return result
        raise WaitCancelException

    async def verify_user(
        self,
        message_chain: Chainable | None = None,
        timeout: float | None = 120,
        delete: bool = True,
    ) -> bool:
        """验证当前操作是否由用户完成。

        :param message_chain: 需要发送的提示消息，可不填
        :param timeout: 等待用户操作的超时时间（秒），默认为 120 秒。
        :param delete: 验证完成或超时后是否删除提示消息，默认为 True。
        :return: 用户选择或发送的数字与目标数字一致时返回 True，否则返回 False。
        :raises WaitCancelException: 如果等待超时或未取得用户输入。
        """
        choices = Random.sample(range(1, 101), 3)
        answer = Random.choice(choices)
        prompt_key = (
            "message.user_verification.prompt.button"
            if self.session_info.support_button
            else "message.user_verification.prompt.text"
        )
        possibly_choices = (
            [{str(choice): str(choice) for choice in choices}] if self.session_info.support_button else None
        )
        s = message_chain
        if message_chain is None:
            s = MessageChain.assign(I18NContext(prompt_key, number=answer))
        else:
            s += I18NContext(prompt_key, number=answer)
        result = await self.wait_next_message(
            s,
            delete=delete,
            timeout=timeout,
            append_instruction=False,
            possibly_choices=possibly_choices,
        )
        return result.as_display(text_only=True).strip() == str(answer)

    async def wait_anyone(
        self,
        message_chain: Chainable | None = None,
        quote: bool = False,
        delete: bool = False,
        timeout: float | None = 120,
    ) -> MessageSession:
        """一次性模板，用于等待触发对象所属场景内任意成员的消息。

        :param message_chain: 需要发送的消息，可不填
        :param quote: 是否引用原始消息（默认为 False）
        :param delete: 是否在触发后删除消息（默认为 False）
        :param timeout: 超时时间（秒），默认为 120 秒
        :return: 任意用户发送的消息的 MessageSession 对象

        :raises WaitCancelException: 如果超时或出错
        """
        send = None
        released_lease = ExecutionLockList.remove(self)
        await self.end_typing()
        flag = asyncio.Event()
        SessionTaskManager.add_task(
            self,
            flag,
            all_=True,
            timeout=timeout,
            task_type="wait_anyone",
            allow_fallthrough=True,
        )
        task_info = None
        try:
            if message_chain:
                chain = get_message_chain(self.session_info, message_chain)
                send = await self.send_message(chain, quote)
            await asyncio.wait_for(flag.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if send and delete:
                await send.delete()
            raise WaitCancelException
        finally:
            task_info = SessionTaskManager.remove_task(self, all_=True)
        if task_info and "result" in task_info:
            if send and delete:
                await send.delete()
            if released_lease and not await ExecutionLockList.acquire(self, wait=True):
                raise WaitCancelException
            return task_info["result"]
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
        """一次性模板，用于等待触发对象回复消息。

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
            chain = get_message_chain(self.session_info, message_chain)
            if append_instruction and isinstance(chain, MessageChain):
                chain.append(I18NContext("message.wait.next_message.prompt"))
            if all_:
                return await self.wait_anyone(chain, False, delete, timeout)
            return await self.wait_next_message(chain, False, delete, timeout, False)

        released_lease = ExecutionLockList.remove(self)
        await self.end_typing()
        chain = get_message_chain(self.session_info, message_chain)
        if append_instruction and isinstance(chain, MessageChain):
            chain.append(I18NContext("message.wait.reply.prompt"))
        send = None
        flag = asyncio.Event()
        SessionTaskManager.add_task(self, flag, all_=all_, reply_pending=True, timeout=timeout)
        try:
            async with asyncio.timeout(timeout):
                send = await self.send_message(chain, quote)
                if not send.message_id or not SessionTaskManager.set_task_reply(self, send.message_id, all_=all_):
                    raise WaitCancelException
                await flag.wait()
        except TimeoutError:
            pass
        finally:
            task_info = SessionTaskManager.remove_task(self, all_=all_)
            if send and delete:
                try:
                    await send.delete()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    Logger.exception("Failed to delete a wait_reply prompt.")
        result = task_info.get("result") if task_info else None
        if result:
            if released_lease and not await ExecutionLockList.acquire(self, wait=True):
                raise WaitCancelException
            return result
        raise WaitCancelException

    async def sleep(self, s: float):
        """
        用于暂停执行指定的秒数。

        :param s: 暂停时长（秒）
        """
        released_lease = ExecutionLockList.remove(self)
        await asyncio.sleep(s)
        if released_lease and not await ExecutionLockList.acquire(self, wait=True):
            raise WaitCancelException

    def check_super_user(self) -> bool:
        """
        用于检查消息用户是否为超级用户。

        :return: 如果用户是超级用户返回 True，否则返回 False
        """
        return bool(self.session_info.sender_union_info.superuser)

    async def check_permission(self) -> bool:
        """用于检查消息用户在场景内的权限。

        :return: 如果用户拥有管理员权限返回 True，否则返回 False
        """
        if (
            self.session_info.sender_union_id in self.session_info.custom_admins
            or self.session_info.sender_union_info.superuser
        ):
            return True
        return await self.check_native_permission()

    async def call_onebot_api(self, api_name: str, **kwargs) -> Any:
        """调用 OneBot API。

        :param api_name: API 名称
        :param kwargs: API 参数
        :return: API 返回结果
        """
        return await PlatformAPI.call_onebot_api(self.session_info, api_name=api_name, **kwargs)

    @deprecated(reason="Use `call_onebot_api` instead.")
    async def call_api(self, api_name: str, **kwargs):
        return await self.call_onebot_api(api_name, **kwargs)

    waitConfirm = wait_confirm
    waitNextMessage = wait_next_message
    verifyUser = verify_user
    waitReply = wait_reply
    waitAnyone = wait_anyone
    checkPermission = check_permission
    checkSuperUser = check_super_user
    sendMessage = send_message
    sendDirectMessage = send_direct_message
    asDisplay = as_display
    checkNativePermission = check_native_permission
    checkBotState = check_bot_state
    callOneBotAPI = call_onebot_api

    def format_time(
        self,
        timestamp: float,
        date: bool = True,
        simple: bool = False,
        time: bool = True,
        seconds: bool = True,
        timezone: bool = True,
    ) -> str:
        """用于将时间戳转换为可读的时间格式。

        :param timestamp: UTC 时间戳
        :param date: 是否显示日期（默认为 True）
        :param simple: 是否以简单格式显示日期（默认为 False）
        :param time: 是否显示时间（默认为 True）
        :param seconds: 是否显示秒（默认为 True）
        :param timezone: 是否显示时区（默认为 True）
        :return: 格式化后的时间字符串
        """
        ftime_template = []
        if date:
            if simple:
                ftime_template.append(self.session_info.locale.t("time.date.simple.format"))
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
        return safe_strftime(
            datetime.fromtimestamp(timestamp, UTC) + self.session_info.timezone_offset,
            " ".join(ftime_template),
        )

    def format_num(self, number: Decimal | int | str, precision: int = 0) -> str:
        """格式化数字为本地化的表示。

        :param number: 要格式化的数字
        :param precision: 保留小数点位数（默认为 0）
        :return: 本地化格式的数字字符串
        """

        def _get_cjk_unit(number: Decimal) -> tuple[int, Decimal] | None:
            # 中日韩文字数单位：万（10^4）亿（10^8）兆（10^12）
            if number >= Decimal("1e12"):
                return 3, Decimal("1e12")
            if number >= Decimal("1e8"):
                return 2, Decimal("1e8")
            if number >= Decimal("1e4"):
                return 1, Decimal("1e4")
            return None

        def _get_unit(number: Decimal) -> tuple[int, Decimal] | None:
            # 英文单位：k（10^3）M（10^6）G（10^9）
            if number >= Decimal("1e9"):
                return 3, Decimal("1e9")
            if number >= Decimal("1e6"):
                return 2, Decimal("1e6")
            if number >= Decimal("1e3"):
                return 1, Decimal("1e3")
            return None

        def _fmt_num(number: Decimal, precision: int) -> str:
            number = number.quantize(Decimal(f"1.{'0' * precision}"), rounding=ROUND_HALF_UP)
            num_str = f"{number:.{precision}f}".rstrip("0").rstrip(".")
            return num_str if precision > 0 else str(int(number))

        if is_int(number):
            number = int(number)
        else:
            return str(number)

        if self.session_info.locale.locale in ["ja_jp", "ko_kr", "zh_cn", "zh_tw"]:
            unit_info = _get_cjk_unit(Decimal(number))
        else:
            unit_info = _get_unit(Decimal(number))

        if not unit_info:
            return str(number)

        unit, scale = unit_info
        fmted_num = _fmt_num(number / scale, precision)
        return self.session_info.locale.t_str(f"{fmted_num} {{I18N:i18n.unit.{unit}}}", locale_failed_prompt=True)

    def __hash__(self):
        return hash(self.session_info.session_id)

    def __eq__(self, other):
        """比较两个消息会话对象是否相等。

        :param other: 另一个对象
        :return: 如果相等返回 True，否则返回 False
        """
        if isinstance(other, MessageSession):
            return self.session_info.session_id == other.session_info.session_id
        return False


@define
class FinishedSession:
    """结束会话类 - 表示已完成的消息发送会话。"""

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
        """用于删除这条消息。"""
        await PlatformAPI.delete_message.submit(self.session, self.message_id)

    def __str__(self):
        """返回字符串表示"""
        return f"FinishedSession(message_id={self.message_id})"


@define
class FetchedMessageSession(MessageSession):
    """主动获取的消息会话。"""

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

__all__ = ["SessionInfo", "MessageSession", "FetchedMessageSession"]
