import asyncio
import random
import re
import time
from collections import OrderedDict, deque
from pathlib import Path

import aiocqhttp
from aiocqhttp import Event, MessageSegment
from tenacity import retry, stop_after_attempt, wait_fixed

from bots.onebot.client import aiocqhttp_bot
from bots.onebot.info import target_private_prefix, target_group_prefix, client_name
from bots.onebot.utils import CQCodeHandler
from core.builtins.filter import filter_badwords
from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, AudioElement, VideoElement, MentionElement
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from bots.onebot.config import AiocqhttpConfig
from core.logger import Logger
from .features import features as onebot_features

qq_typing_emoji = str(AiocqhttpConfig.qq_typing_emoji)
qq_limited_emoji = str(AiocqhttpConfig.qq_limited_emoji)
qq_initiative_msg_cooldown = AiocqhttpConfig.qq_initiative_msg_cooldown
TYPING_CACHE_TTL = 3600
TYPING_CACHE_MAX_SIZE = 4096
TYPING_MAX_LIFETIME = 60
INITIATIVE_QUEUE_MAX_SIZE = 128
HIGH_PRIORITY_BURST = 5
HIGH_PRIORITY_QUEUE_RESERVE = 16
last_send_typing_time: OrderedDict[str, float] = OrderedDict()


def _typing_prompt_on_cooldown(sender_id: str, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    last_sent = last_send_typing_time.get(sender_id)
    while last_send_typing_time:
        oldest_sender, oldest_time = next(iter(last_send_typing_time.items()))
        if len(last_send_typing_time) <= TYPING_CACHE_MAX_SIZE and now - oldest_time <= TYPING_CACHE_TTL:
            break
        last_send_typing_time.pop(oldest_sender, None)
    return last_sent is not None and now - last_sent <= TYPING_CACHE_TTL


def _record_typing_prompt(sender_id: str, now: float | None = None) -> None:
    last_send_typing_time.pop(sender_id, None)
    last_send_typing_time[sender_id] = time.monotonic() if now is None else now
    while len(last_send_typing_time) > TYPING_CACHE_MAX_SIZE:
        last_send_typing_time.popitem(last=False)


async def fake_forward_msg(session_info: SessionInfo, nodelist):
    if session_info.target_from == target_group_prefix:
        return await aiocqhttp_bot.call_action(
            "send_group_forward_msg",
            group_id=int(session_info.get_common_target_id()),
            messages=nodelist,
        )
    if session_info.target_from == target_private_prefix:
        return await aiocqhttp_bot.call_action(
            "send_private_forward_msg", user_id=int(session_info.get_common_sender_id()), messages=nodelist
        )


def convert_msg_nodes(
    session_info: SessionInfo,
    msg_node: MessageNodes,
) -> list[dict]:
    node_list = []
    for message in msg_node.values:
        content = ""
        msg_chain = message.as_sendable(session_info=session_info)
        for x in msg_chain:
            if isinstance(x, PlainElement):
                content += session_info.locale.t_str(filter_badwords(x.text)) + "\n"
            elif isinstance(x, ImageElement):
                content += f"[CQ:image,file=base64://{x.get_base64()}]\n"

        template = {
            "type": "node",
            "data": {
                "nickname": Temp.data.get("qq_nickname"),
                "user_id": str(Temp.data.get("qq_account")),
                "content": content.strip(),
            },
        }
        node_list.append(template)
    return node_list


async def get_available_group_list():
    """
    获取可用的群组列表。

    :return: 群组列表
    """
    group_list = []
    try:
        groups = await aiocqhttp_bot.call_action("get_group_list")
        for group in groups:
            group_list.append(group.get("group_id"))
    except aiocqhttp.exceptions.ActionFailed as e:
        Logger.error(f"Failed to get group list: {e}")
    return group_list


async def get_available_private_list():
    """
    获取可用的私聊列表。

    :return: 私聊列表
    """
    private_list = []
    try:
        friends = await aiocqhttp_bot.call_action("get_friend_list")
        for friend in friends:
            private_list.append(friend.get("user_id"))
    except aiocqhttp.exceptions.ActionFailed as e:
        Logger.error(f"Failed to get private list: {e}")
    return private_list


class OneBotContextManager(ContextManager):
    context: dict[str, Event] = {}
    features: Features = onebot_features
    typing_tasks: dict[str, asyncio.Task[None]] = {}
    TYPING_SHUTDOWN_TIMEOUT = 1.0

    @classmethod
    async def shutdown(cls) -> None:
        """释放 OneBot 适配器持有的输入状态任务与生命周期缓存。"""
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
        last_send_typing_time.clear()

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # 这里可以添加权限检查的逻辑

        @retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
        async def _check():
            if session_info.target_from == target_private_prefix:
                return True
            if session_info.target_from == target_group_prefix:
                get_member_info = await aiocqhttp_bot.call_action(
                    "get_group_member_info",
                    group_id=int(session_info.get_common_target_id()),
                    user_id=int(session_info.get_common_sender_id()),
                )
                if get_member_info.get("role") in ["owner", "admin"]:
                    return True
            return False

        return await _check()

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        # ctx: Event = cls.context.get(session_info.session_id)
        send = None
        if session_info.sender_id is None:
            if session_info.target_from == target_group_prefix:
                group_list = await get_available_group_list()
                if group_list:
                    if int(session_info.get_common_target_id()) not in group_list:
                        Logger.warning("Group not found in group list, skipping message send.")
                        return []
            if session_info.target_from == target_private_prefix:
                private_list = await get_available_private_list()
                if private_list:
                    if int(session_info.get_common_target_id()) not in private_list:
                        Logger.warning("Private chat not found in private list, skipping message send.")
                        return []

        if isinstance(message, MessageNodes):
            send = await fake_forward_msg(session_info, convert_msg_nodes(session_info, message))

        else:
            convert_msg_segments = MessageSegment.text("")
            if quote and session_info.target_from == target_group_prefix and session_info.messages:
                convert_msg_segments = MessageSegment.reply(int(session_info.message_id))

            count = 0
            for x in message.as_sendable(session_info):
                if isinstance(x, PlainElement):
                    x.text = session_info.locale.t_str(filter_badwords(x.text))
                    if x.allow_parse:
                        x.text = match_atcode(x.text, client_name, "[CQ:at,qq={uid}]")
                    if x.allow_parse:
                        parts = re.split(r"(\[CQ:[^\]]+\])", x.text)
                        parts = [part for part in parts if part]
                        previous_was_cq = False
                        # CQ码消息段相连会导致自动转义，故使用零宽字符`\u200B`隔开
                        for i, part in enumerate(parts):
                            if re.match(r"\[CQ:[^\]]+\]", part):
                                try:
                                    cq_data = CQCodeHandler.parse_cq(part)
                                    if cq_data:
                                        if previous_was_cq:
                                            convert_msg_segments = convert_msg_segments + MessageSegment.text("\u200b")
                                        convert_msg_segments = (
                                            convert_msg_segments
                                            + MessageSegment.text("\n" if (count != 0 and i == 0) else "")
                                            + MessageSegment(type_=cq_data["type"], data=cq_data["data"])
                                        )
                                    else:
                                        if previous_was_cq:
                                            convert_msg_segments = convert_msg_segments + MessageSegment.text("\u200b")
                                        convert_msg_segments = convert_msg_segments + MessageSegment.text(
                                            ("\n" if (count != 0 and i == 0) else "") + part
                                        )
                                except Exception:
                                    if previous_was_cq:
                                        convert_msg_segments = convert_msg_segments + MessageSegment.text("\u200b")
                                    convert_msg_segments = convert_msg_segments + MessageSegment.text(
                                        ("\n" if (count != 0 and i == 0) else "") + part
                                    )
                                finally:
                                    previous_was_cq = True
                            else:
                                convert_msg_segments = convert_msg_segments + MessageSegment.text(
                                    ("\n" if count != 0 else "") + part
                                )
                                previous_was_cq = False
                    else:
                        convert_msg_segments = convert_msg_segments + MessageSegment.text(
                            ("\n" if count != 0 else "") + x.text
                        )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
                    count += 1
                elif isinstance(x, ImageElement):
                    convert_msg_segments = convert_msg_segments + MessageSegment.image(
                        "base64://" + await x.get_base64()
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(x)}")
                    count += 1
                elif isinstance(x, AudioElement):
                    convert_msg_segments = convert_msg_segments + MessageSegment.record(file=Path(x.path).as_uri())
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Audio: {str(x)}")
                    count += 1
                elif isinstance(x, VideoElement):
                    convert_msg_segments = convert_msg_segments + MessageSegment.video(file=Path(x.path).as_uri())
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Audio: {str(x)}")
                    count += 1
                elif isinstance(x, MentionElement):
                    if x.client == client_name and session_info.target_from == target_group_prefix:
                        convert_msg_segments = convert_msg_segments + MessageSegment.at(x.id)
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{str(x.id)}")
                    else:
                        convert_msg_segments = convert_msg_segments + MessageSegment.text(" ")
                    count += 1

            if session_info.target_from == target_group_prefix:
                try:
                    send = await aiocqhttp_bot.send_group_msg(
                        group_id=int(session_info.get_common_target_id()), message=convert_msg_segments
                    )
                except aiocqhttp.exceptions.NetworkError:
                    send = await aiocqhttp_bot.send_group_msg(
                        group_id=int(session_info.get_common_target_id()),
                        message=MessageSegment.text(session_info.locale.t("error.message.timeout")),
                    )
                except aiocqhttp.exceptions.ActionFailed:
                    send = await aiocqhttp_bot.send_group_msg(
                        group_id=int(session_info.get_common_target_id()),
                        message=MessageSegment.text(session_info.locale.t("error.message.limited")),
                    )
                    Logger.exception("Failed to send message: ")

            else:
                try:
                    send = await aiocqhttp_bot.send_private_msg(
                        user_id=int(session_info.get_common_target_id()), message=convert_msg_segments
                    )
                except aiocqhttp.exceptions.ActionFailed:
                    Logger.exception("Failed to send message: ")
        if send:
            return [str(send["message_id"])]
        return []

    @classmethod
    async def send_private_msg(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
    ) -> list[str]:
        uid = user_id.split("|")[-1]
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

            # 显式指定基类：主动消息所用的子类会将发送放入冷却队列并返回 None，无法取得消息 ID
            return await OneBotContextManager.send_message(
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

        if session_info.target_from in [target_private_prefix, target_group_prefix]:
            for x in message_id:
                try:
                    await aiocqhttp_bot.call_action("delete_msg", message_id=x)
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
        if session_info.target_from == target_group_prefix:
            for x in user_id:
                try:
                    await aiocqhttp_bot.call_action(
                        "set_group_ban",
                        group_id=session_info.get_common_target_id(),
                        user_id=x.split("|")[-1],
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

        if session_info.target_from == target_group_prefix:
            for x in user_id:
                try:
                    await aiocqhttp_bot.call_action(
                        "set_group_ban",
                        group_id=session_info.get_common_target_id(),
                        user_id=x.split("|")[-1],
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

        if session_info.target_from == target_group_prefix:
            for x in user_id:
                try:
                    await aiocqhttp_bot.call_action(
                        "set_group_kick",
                        group_id=session_info.get_common_target_id(),
                        user_id=x.split("|")[-1],
                        reject_add_request=False,
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

        if session_info.target_from == target_group_prefix:
            for x in user_id:
                try:
                    await aiocqhttp_bot.call_action(
                        "set_group_kick",
                        group_id=session_info.get_common_target_id(),
                        user_id=x.split("|")[-1],
                        reject_add_request=True,
                    )
                    Logger.info(f"Banned member {x} in group {session_info.target_id}")
                except Exception:
                    Logger.exception(f"Failed to ban member {x} in group {session_info.target_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if session_info.target_from == target_group_prefix:
            try:
                obi = Temp.data.get("onebot_impl")
                if obi in ["llonebot", "napcat"]:
                    await aiocqhttp_bot.call_action(
                        "set_msg_emoji_like", message_id=message_id[-1], emoji_id=emoji, set=True
                    )
                elif obi == "lagrange":
                    await aiocqhttp_bot.call_action(
                        "set_group_reaction",
                        group_id=int(session_info.get_common_target_id()),
                        message_id=message_id[-1],
                        code=emoji,
                        is_add=True,
                    )
                else:
                    return
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

        if session_info.target_from == target_group_prefix:
            try:
                obi = Temp.data.get("onebot_impl")
                if obi in ["llonebot", "napcat"]:
                    await aiocqhttp_bot.call_action(
                        "set_msg_emoji_like", message_id=message_id[-1], emoji_id=emoji, set=False
                    )
                elif obi == "lagrange":
                    await aiocqhttp_bot.call_action(
                        "set_group_reaction",
                        group_id=int(session_info.get_common_target_id()),
                        message_id=message_id[-1],
                        code=emoji,
                        is_add=False,
                    )
                else:
                    return
                Logger.info(f'Removed reaction "{emoji}" to message {message_id} in session {session_info.session_id}')
            except Exception:
                Logger.exception(
                    f'Failed to remove reaction "{emoji}" to message {message_id} in session {
                        session_info.session_id
                    }: '
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

        async def _typing():
            try:
                async with asyncio.timeout(TYPING_MAX_LIFETIME):
                    Logger.debug(f"Start typing in session: {session_info.session_id}")

                    if session_info.target_from == target_group_prefix:  # wtf onebot 11
                        obi = Temp.data.get("onebot_impl")
                        if obi in ["llonebot", "napcat"]:
                            await aiocqhttp_bot.call_action(
                                "set_msg_emoji_like",
                                message_id=session_info.message_id,
                                emoji_id=qq_typing_emoji,
                                set=True,
                            )
                        elif obi == "lagrange":
                            await aiocqhttp_bot.call_action(
                                "set_group_reaction",
                                group_id=int(session_info.get_common_target_id()),
                                message_id=session_info.message_id,
                                code=qq_typing_emoji,
                                is_add=True,
                            )
                        elif obi in ["shamrock", "go-cqhttp"] and not _typing_prompt_on_cooldown(
                            session_info.sender_id
                        ):
                            if obi == "shamrock":
                                await aiocqhttp_bot.send_group_msg(
                                    group_id=int(session_info.get_common_target_id()),
                                    message=f"[CQ:touch,id={session_info.get_common_sender_id()}]",
                                )
                            else:
                                await aiocqhttp_bot.send_group_msg(
                                    group_id=int(session_info.get_common_target_id()),
                                    message=f"[CQ:poke,qq={session_info.get_common_sender_id()}]",
                                )
                            _record_typing_prompt(session_info.sender_id)
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
            _typing(), name=f"onebot-typing-{session_info.session_id}"
        )

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        flag = cls.typing_flags.pop(session_info.session_id, None)
        if flag:
            flag.set()
        task = cls.typing_tasks.pop(session_info.session_id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        # 这里可以添加结束输入状态的逻辑
        Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加错误处理逻辑

        if session_info.target_from == target_group_prefix:
            qq_account = Temp.data.get("qq_account")
            obi = Temp.data.get("onebot_impl")
            if obi in ["llonebot", "napcat"]:
                await aiocqhttp_bot.call_action(
                    "set_msg_emoji_like", message_id=session_info.message_id, emoji_id=qq_limited_emoji, set=True
                )
            elif obi == "lagrange":
                await aiocqhttp_bot.call_action(
                    "set_group_reaction",
                    group_id=int(session_info.get_common_target_id()),
                    message_id=session_info.message_id,
                    code=qq_limited_emoji,
                    is_add=True,
                )
            elif obi == "shamrock":
                await aiocqhttp_bot.call_action(
                    "send_group_msg",
                    group_id=int(session_info.get_common_target_id()),
                    message=f"[CQ:touch,id={qq_account}]",
                )
            elif obi == "go-cqhttp":
                await aiocqhttp_bot.call_action(
                    "send_group_msg",
                    group_id=int(session_info.get_common_target_id()),
                    message=f"[CQ:poke,qq={qq_account}]",
                )
            else:
                pass

    @classmethod
    async def call_onebot_api(cls, api_name: str, **kwargs) -> dict | None:
        return await aiocqhttp_bot.call_action(api_name, **kwargs)


_tasks_high_priority = deque()
_tasks = deque()


class OneBotFetchedContextManager(OneBotContextManager):
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
            Logger.warning(f"OneBot initiative message queue is full; dropped message to {session_info.target_id}.")
            return []
        if high_priority and queue_size >= INITIATIVE_QUEUE_MAX_SIZE:
            if _tasks:
                evicted_future = _tasks.popleft()[0]
                if not evicted_future.done():
                    evicted_future.set_result([])
            else:
                Logger.warning(
                    f"OneBot high-priority initiative message queue is full; dropped message to {session_info.target_id}."
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
            result = await OneBotContextManager.send_message(
                session_info,
                message,
                quote=quote,
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
            cls._processor_task = asyncio.create_task(cls.process_tasks(), name="onebot-initiative-message-worker")
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
        while True:
            try:
                queued_task = OneBotFetchedContextManager._take_next_task()
                if queued_task is None:
                    await asyncio.sleep(1)
                    continue
                task, high_priority = queued_task
                await OneBotFetchedContextManager._run_task(task)
                if high_priority:
                    cd = random.randint(1, 5)
                    Logger.info(
                        f"Processed a high-priority task in OneBotFetchedContextManager, waiting cooldown for {cd}s..."
                    )
                else:
                    cd = random.randint(5, max(5, qq_initiative_msg_cooldown))
                    Logger.info(f"Processed a task in OneBotFetchedContextManager, waiting cooldown for {cd}s...")
                await asyncio.sleep(cd)
            except asyncio.CancelledError:
                raise
            except Exception:
                Logger.exception("OneBot initiative message worker failed to process a task: ")
                await asyncio.sleep(1)
