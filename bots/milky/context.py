import asyncio
import random
from collections import deque

from milky.async_client import MilkyError, MilkyHttpError
from milky.models import OutgoingTextSegment, Role, TextSegmentData
from tenacity import retry, stop_after_attempt, wait_fixed

from bots.milky.client import milky_bot
from bots.milky.config import MilkyConfig
from bots.milky.features import features as milky_features
from bots.milky.info import target_group_prefix, target_private_prefix
from bots.milky.utils import (
    convert_chain_to_segments,
    convert_msg_nodes,
    get_available_group_list,
    get_available_private_list,
)
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.bot_state import BotState
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.logger import Logger

qq_typing_emoji = str(MilkyConfig.qq_typing_emoji)
qq_limited_emoji = str(MilkyConfig.qq_limited_emoji)
qq_initiative_msg_cooldown = MilkyConfig.qq_initiative_msg_cooldown

TYPING_MAX_LIFETIME = 60
INITIATIVE_QUEUE_MAX_SIZE = 128
HIGH_PRIORITY_BURST = 5
HIGH_PRIORITY_QUEUE_RESERVE = 16


def _split_common_id(user_id: str) -> str:
    return str(user_id).split("|")[-1]


class MilkyContextManager(ContextManager):
    context: dict[str, dict] = {}
    features: Features = milky_features
    typing_tasks: dict[str, asyncio.Task[None]] = {}
    TYPING_SHUTDOWN_TIMEOUT = 1.0

    @classmethod
    async def shutdown(cls) -> None:
        """释放 Milky 适配器持有的输入状态任务。"""
        for flag in tuple(cls.typing_flags.values()):
            flag.set()

        current = asyncio.current_task()
        tasks = {task for task in cls.typing_tasks.values() if task is not current}
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=cls.TYPING_SHUTDOWN_TIMEOUT)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        cls.typing_flags.clear()
        cls.typing_tasks.clear()

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        """检查发送者是否具备群管理权限。"""

        @retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
        async def _check() -> bool:
            if session_info.target_from == target_private_prefix:
                return True
            if session_info.target_from == target_group_prefix:
                member = await milky_bot.get_group_member_info(
                    group_id=int(session_info.get_common_target_id()),
                    user_id=int(session_info.get_common_sender_id()),
                )
                if member.role in (Role.OWNER, Role.ADMIN):
                    return True
            return False

        return await _check()

    @classmethod
    async def check_bot_state(cls, session_info: SessionInfo) -> BotState:
        """查询机器人在当前场景中的成员与权限状态。"""
        if session_info.target_from == target_private_prefix:
            return BotState(
                available=True,
                joined=True,
                is_owner=None,
                is_admin=None,
                can_read_messages=True,
                can_read_all_messages=True,
                can_send_messages=True,
                can_send_proactive_messages=True,
                can_manage_messages=None,
                can_manage_members=None,
                can_restrict_members=None,
                can_react=None,
                can_send_private_messages=True,
                raw={"message_scene": "friend"},
            )
        if session_info.target_from != target_group_prefix:
            return BotState(available=None, joined=None, error="Milky context is not a group or private chat")

        bot_id = session_info.bot_id or Temp.data.get("qq_account")
        if bot_id is None:
            return BotState(available=None, joined=None, error="Milky bot ID is unavailable")
        try:
            member = await milky_bot.get_group_member_info(
                group_id=int(session_info.get_common_target_id()),
                user_id=int(_split_common_id(bot_id)),
            )
            is_owner = member.role == Role.OWNER
            is_admin = member.role in (Role.OWNER, Role.ADMIN)
            return BotState(
                available=True,
                joined=True,
                is_owner=is_owner,
                is_admin=is_admin,
                can_read_messages=True,
                can_read_all_messages=None,
                can_send_messages=True,
                can_send_proactive_messages=True,
                can_manage_messages=is_admin,
                can_manage_members=is_admin,
                can_restrict_members=is_admin,
                can_react=True,
                can_send_private_messages=True,
                permissions={"role": str(member.role)},
                raw=member.model_dump(),
            )
        except Exception as exc:
            Logger.exception(f"Failed to check Milky bot state in {session_info.target_id}: ")
            return BotState(available=None, joined=None, error=str(exc))

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        if session_info.sender_id is None:
            # 主动消息：目标可能已退群或删除好友，先查询列表以避免无效请求
            if session_info.target_from == target_group_prefix:
                group_list = await get_available_group_list()
                if group_list and int(session_info.get_common_target_id()) not in group_list:
                    Logger.warning("Group not found in group list, skipping message send.")
                    return []
            elif session_info.target_from == target_private_prefix:
                private_list = await get_available_private_list()
                if private_list and int(session_info.get_common_target_id()) not in private_list:
                    Logger.warning("Private chat not found in private list, skipping message send.")
                    return []

        if isinstance(message, MessageNodes):
            forward_segment = await convert_msg_nodes(session_info, message)
            if forward_segment is None:
                return []
            segments: list = [forward_segment]
        else:
            segments = await convert_chain_to_segments(session_info, message, quote=quote)

        if not segments:
            # 元素均因底层媒体不可得被跳过时不发送空消息
            return []

        try:
            target_id = int(session_info.get_common_target_id())
            if session_info.target_from == target_group_prefix:
                result = await milky_bot.send_group_message(group_id=target_id, message=segments)
            else:
                result = await milky_bot.send_private_message(user_id=target_id, message=segments)
            return [str(result.message_seq)]
        except asyncio.CancelledError:
            raise
        except (MilkyError, MilkyHttpError):
            Logger.exception(f"Failed to send message to {session_info.target_id}: ")
            try:
                # 协议端拒绝消息内容时回退为提示文本，保证调用方仍能感知本跳失败
                fallback = OutgoingTextSegment(
                    data=TextSegmentData(text=session_info.locale.t("error.message.limited"))
                )
                if session_info.target_from == target_group_prefix:
                    result = await milky_bot.send_group_message(group_id=target_id, message=[fallback])
                else:
                    result = await milky_bot.send_private_message(user_id=target_id, message=[fallback])
                return [str(result.message_seq)]
            except asyncio.CancelledError:
                raise
            except Exception:
                Logger.exception(f"Failed to send fallback notice to {session_info.target_id}: ")
                return []

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
    ) -> list[str]:
        uid = _split_common_id(user_id)
        if not uid.isdigit():
            Logger.warning(f"Invalid user id {user_id}, cannot send private message.")
            return []

        try:
            # 未添加机器人为好友时私聊必然无法送达，先查询好友列表以避免无效请求。
            # 查询本身同样属于平台调用，网络错误等异常必须遵守私信失败返回空 ID 的契约。
            private_list = await get_available_private_list()
            if private_list and int(uid) not in private_list:
                Logger.warning(f"User {uid} not found in private list, skipping private message send.")
                return []

            # 显式指定基类：主动消息所用的子类会将发送放入冷却队列并返回空结果，取不到消息 ID
            return await MilkyContextManager.send_message(
                cls.derive_private_session(session_info, f"{target_private_prefix}|{uid}", target_private_prefix),
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

        if session_info.target_from not in (target_private_prefix, target_group_prefix):
            return
        for x in message_id:
            if not str(x).isdigit():
                Logger.warning(f"Invalid message id {x}, cannot recall message.")
                continue
            try:
                if session_info.target_from == target_group_prefix:
                    await milky_bot.recall_group_message(
                        group_id=int(session_info.get_common_target_id()), message_seq=int(x)
                    )
                else:
                    await milky_bot.recall_private_message(
                        user_id=int(session_info.get_common_target_id()), message_seq=int(x)
                    )
                Logger.info(f"Deleted message {x} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to delete message {x} in session {session_info.session_id}: ")

    @classmethod
    async def restrict_member(
        cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None = None, reason: str | None = None
    ) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if not duration:
            duration = 1800
        if session_info.target_from != target_group_prefix:
            return
        for x in user_id:
            try:
                await milky_bot.set_group_member_mute(
                    group_id=int(session_info.get_common_target_id()),
                    user_id=int(_split_common_id(x)),
                    duration=duration,
                )
                Logger.info(f"Restricted member {x} ({duration}s) in group {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to restrict member {x} in group {session_info.target_id}: ")

    @classmethod
    async def unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from != target_group_prefix:
            return
        for x in user_id:
            try:
                await milky_bot.set_group_member_mute(
                    group_id=int(session_info.get_common_target_id()),
                    user_id=int(_split_common_id(x)),
                    duration=0,
                )
                Logger.info(f"Unrestricted member {x} in group {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to unrestrict member {x} in group {session_info.target_id}: ")

    @classmethod
    async def kick_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from != target_group_prefix:
            return
        for x in user_id:
            try:
                await milky_bot.kick_group_member(
                    group_id=int(session_info.get_common_target_id()),
                    user_id=int(_split_common_id(x)),
                )
                Logger.info(f"Kicked member {x} in group {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to kick member {x} in group {session_info.target_id}: ")

    @classmethod
    async def ban_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")

        if session_info.target_from != target_group_prefix:
            return
        for x in user_id:
            try:
                await milky_bot.kick_group_member(
                    group_id=int(session_info.get_common_target_id()),
                    user_id=int(_split_common_id(x)),
                    reject_add_request=True,
                )
                Logger.info(f"Banned member {x} in group {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to ban member {x} in group {session_info.target_id}: ")

    @classmethod
    async def grant_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if isinstance(permission_group_id, str):
            permission_group_id = [permission_group_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")
        if not isinstance(permission_group_id, list):
            raise TypeError("Permission group ID must be a list or str")

        if session_info.target_from != target_group_prefix:
            return
        if "admin" not in {str(x).lower() for x in permission_group_id}:
            Logger.warning(f"Milky does not support permission group(s) {permission_group_id}, skipping.")
            return
        for x in user_id:
            try:
                await milky_bot.set_group_member_admin(
                    group_id=int(session_info.get_common_target_id()),
                    user_id=int(_split_common_id(x)),
                    is_set=True,
                )
                Logger.info(f"Granted admin of {x} in group {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to grant admin of {x} in group {session_info.target_id}: ")

    @classmethod
    async def revoke_permission_group(
        cls,
        session_info: SessionInfo,
        user_id: str | list[str],
        permission_group_id: str | list[str],
        reason: str | None = None,
    ) -> None:
        if isinstance(user_id, str):
            user_id = [user_id]
        if isinstance(permission_group_id, str):
            permission_group_id = [permission_group_id]
        if not isinstance(user_id, list):
            raise TypeError("User ID must be a list or str")
        if not isinstance(permission_group_id, list):
            raise TypeError("Permission group ID must be a list or str")

        if session_info.target_from != target_group_prefix:
            return
        # Milky 只暴露「管理员」这一原生权限组，其它权限组在本平台没有对应实现
        if "admin" not in {str(x).lower() for x in permission_group_id}:
            Logger.warning(f"Milky does not support permission group(s) {permission_group_id}, skipping.")
            return
        for x in user_id:
            try:
                await milky_bot.set_group_member_admin(
                    group_id=int(session_info.get_common_target_id()),
                    user_id=int(_split_common_id(x)),
                    is_set=False,
                )
                Logger.info(f"Revoked admin of {x} in group {session_info.target_id}")
            except Exception:
                Logger.exception(f"Failed to revoke admin of {x} in group {session_info.target_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if not message_id:
            return
        # Milky 仅支持群聊消息表情回应，且 SDK 固定以 `face` 类型发送回应
        if session_info.target_from != target_group_prefix:
            Logger.debug("Milky only supports message reactions in group chats, skipping.")
            return
        message_seq = message_id[-1]
        if not str(message_seq).isdigit():
            Logger.warning(f"Invalid message id {message_seq}, cannot send reaction.")
            return
        try:
            await milky_bot.send_group_message_reaction(
                group_id=int(session_info.get_common_target_id()),
                message_seq=int(message_seq),
                reaction=str(emoji),
                is_add=True,
            )
            Logger.info(f'Added reaction "{emoji}" to message {message_seq} in session {session_info.session_id}')
        except Exception:
            Logger.exception(
                f'Failed to add reaction "{emoji}" to message {message_seq} in session {session_info.session_id}: '
            )

    @classmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if not message_id:
            return
        # Milky 仅支持群聊消息表情回应，且 SDK 固定以 `face` 类型发送回应
        if session_info.target_from != target_group_prefix:
            Logger.debug("Milky only supports message reactions in group chats, skipping.")
            return
        message_seq = message_id[-1]
        if not str(message_seq).isdigit():
            Logger.warning(f"Invalid message id {message_seq}, cannot send reaction.")
            return
        try:
            await milky_bot.send_group_message_reaction(
                group_id=int(session_info.get_common_target_id()),
                message_seq=int(message_seq),
                reaction=str(emoji),
                is_add=False,
            )
            Logger.info(f'Removed reaction "{emoji}" to message {message_seq} in session {session_info.session_id}')
        except Exception:
            Logger.exception(
                f'Failed to remove reaction "{emoji}" to message {message_seq} in session {session_info.session_id}: '
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

        async def _typing() -> None:
            try:
                async with asyncio.timeout(TYPING_MAX_LIFETIME):
                    Logger.debug(f"Start typing in session: {session_info.session_id}")
                    if session_info.message_id:
                        await cls.add_reaction(session_info, session_info.message_id, qq_typing_emoji)
                    await flag.wait()
            except TimeoutError:
                Logger.debug(f"Typing state expired in session: {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to start typing in session {session_info.session_id}: ")
            finally:
                if cls.typing_flags.get(session_info.session_id) is flag:
                    cls.typing_flags.pop(session_info.session_id, None)
                current_task = asyncio.current_task()
                if cls.typing_tasks.get(session_info.session_id) is current_task:
                    cls.typing_tasks.pop(session_info.session_id, None)

        cls.typing_tasks[session_info.session_id] = asyncio.create_task(
            _typing(), name=f"milky-typing-{session_info.session_id}"
        )

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        flag = cls.typing_flags.pop(session_info.session_id, None)
        if flag:
            flag.set()
        task = cls.typing_tasks.pop(session_info.session_id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if session_info.target_from == target_group_prefix and session_info.message_id:
            await cls.add_reaction(session_info, session_info.message_id, qq_limited_emoji)


_tasks_high_priority = deque()
_tasks = deque()


class MilkyFetchedContextManager(MilkyContextManager):
    """主动消息上下文管理器：协议端主动消息按冷却排队发送。"""

    _processor_task: asyncio.Task[None] | None = None
    _high_priority_count = 0

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        # 主动消息须按冷却排队发出，但调用方需要取得真实的消息 ID 才能判断本跳是否送达，
        # 因此入队的是「任务 + future」，待实际发送完成后再回传结果。
        future = asyncio.get_running_loop().create_future()
        high_priority = session_info.target_union_info.target_data.get("in_post_whitelist", False)
        append_tsk = _tasks_high_priority if high_priority else _tasks
        queue_size = len(_tasks_high_priority) + len(_tasks)
        if not high_priority and queue_size >= INITIATIVE_QUEUE_MAX_SIZE - HIGH_PRIORITY_QUEUE_RESERVE:
            Logger.warning(f"Milky initiative message queue is full; dropped message to {session_info.target_id}.")
            return []
        if high_priority and queue_size >= INITIATIVE_QUEUE_MAX_SIZE:
            if _tasks:
                evicted_future = _tasks.popleft()[0]
                if not evicted_future.done():
                    evicted_future.set_result([])
            else:
                Logger.warning(
                    f"Milky high-priority initiative message queue is full; "
                    f"dropped message to {session_info.target_id}."
                )
                return []
        task = (future, session_info, message, quote)
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
        future, session_info, message, quote = task
        if future.cancelled():
            return
        try:
            result = await MilkyContextManager.send_message(session_info, message, quote=quote)
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
            cls._processor_task = asyncio.create_task(cls.process_tasks(), name="milky-initiative-message-worker")
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
    async def process_tasks() -> None:
        while True:
            try:
                queued_task = MilkyFetchedContextManager._take_next_task()
                if queued_task is None:
                    await asyncio.sleep(1)
                    continue
                task, high_priority = queued_task
                await MilkyFetchedContextManager._run_task(task)
                if high_priority:
                    cd = random.randint(1, 5)
                    Logger.info(
                        f"Processed a high-priority task in MilkyFetchedContextManager, waiting cooldown for {cd}s..."
                    )
                else:
                    cd = random.randint(5, max(5, qq_initiative_msg_cooldown))
                    Logger.info(f"Processed a task in MilkyFetchedContextManager, waiting cooldown for {cd}s...")
                await asyncio.sleep(cd)
            except asyncio.CancelledError:
                raise
            except Exception:
                Logger.exception("Milky initiative message worker failed to process a task: ")
                await asyncio.sleep(1)
