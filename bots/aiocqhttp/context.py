import asyncio
import random
import re
import time
from pathlib import Path

import aiocqhttp
from aiocqhttp import Event, MessageSegment
from tenacity import retry, stop_after_attempt, wait_fixed

from bots.aiocqhttp.client import aiocqhttp_bot
from bots.aiocqhttp.info import target_private_prefix, target_group_prefix, client_name
from bots.aiocqhttp.utils import CQCodeHandler
from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement
from core.builtins.message.internal import I18NContext
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.config import Config
from core.logger import Logger
from core.utils.image import msgchain2image
from .features import Features

qq_typing_emoji = str(Config("qq_typing_emoji", 181, (str, int), table_name="bot_aiocqhttp"))
qq_limited_emoji = str(Config("qq_limited_emoji", 10060, (str, int), table_name="bot_aiocqhttp"))
qq_initiative_msg_cooldown = Config("qq_initiative_msg_cooldown", 10, int, table_name="bot_aiocqhttp")
last_send_typing_time = {}


async def fake_forward_msg(session_info: SessionInfo, nodelist):
    if session_info.target_from == target_group_prefix:
        return await aiocqhttp_bot.call_action(
            "send_group_forward_msg",
            group_id=int(session_info.get_common_target_id()),
            messages=nodelist,
        )
    if session_info.target_from == target_private_prefix:
        return await aiocqhttp_bot.call_action(
            "send_private_forward_msg",
            user_id=int(session_info.get_common_sender_id()),
            messages=nodelist
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
                content += x.text + "\n"
            elif isinstance(x, ImageElement):
                content += f"[CQ:image,file=base64://{x.get_base64()}]\n"

        template = {
            "type": "node",
            "data": {
                "nickname": Temp.data.get("qq_nickname"),
                "user_id": str(Temp.data.get("qq_account")),
                "content": content.strip()
            }
        }
        node_list.append(template)
    return node_list


async def get_avaliable_group_list():
    """
    获取可用的群组列表。

    :return: 群组列表
    """
    group_list = []
    try:
        groups = await aiocqhttp_bot.call_action("get_group_list")
        for group in groups:
            group_list.append(group["group_id"])
    except aiocqhttp.exceptions.ActionFailed as e:
        Logger.error(f"Failed to get group list: {e}")
    return group_list


async def get_avaliable_private_list():
    """
    获取可用的私聊列表。

    :return: 私聊列表
    """
    private_list = []
    try:
        friends = await aiocqhttp_bot.call_action("get_friend_list")
        for friend in friends:
            private_list.append(friend["user_id"])
    except aiocqhttp.exceptions.ActionFailed as e:
        Logger.error(f"Failed to get private list: {e}")
    return private_list


class AIOCQContextManager(ContextManager):
    context: dict[str, Event] = {}
    features: Features | None = Features

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
                if get_member_info["role"] in ["owner", "admin"]:
                    return True
            return False

        return await _check()

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: MessageChain | MessageNodes,
                           quote: bool = True,
                           enable_parse_message=True,
                           enable_split_image=True, ) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        # ctx: Event = cls.context.get(session_info.session_id)
        send = None
        if session_info.sender_id is None:
            if session_info.target_from == target_group_prefix:
                group_list = await get_avaliable_group_list()
                if group_list:
                    if int(session_info.get_common_target_id()) not in group_list:
                        Logger.warning("Group not found in group list, skipping message send.")
                        return []
            if session_info.target_from == target_private_prefix:
                private_list = await get_avaliable_private_list()
                if private_list:
                    if int(session_info.get_common_target_id()) not in private_list:
                        Logger.warning("Private chat not found in private list, skipping message send.")
                        return []

        if isinstance(message, MessageNodes):
            send = await fake_forward_msg(session_info, convert_msg_nodes(session_info, message))

        else:
            convert_msg_segments = MessageSegment.text("")
            if (
                quote
                and session_info.target_from == target_group_prefix
                and session_info.messages
            ):
                convert_msg_segments = MessageSegment.reply(int(session_info.message_id))

            count = 0
            for x in message.as_sendable(session_info, parse_message=enable_parse_message):
                if isinstance(x, PlainElement):
                    if enable_parse_message:
                        x.text = match_atcode(x.text, client_name, "[CQ:at,qq={uid}]")
                    if enable_parse_message:
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
                                            convert_msg_segments = (
                                                convert_msg_segments
                                                + MessageSegment.text("\u200B")
                                            )
                                        convert_msg_segments = (
                                            convert_msg_segments
                                            + MessageSegment.text(
                                                "\n" if (count != 0 and i == 0) else ""
                                            )
                                            + MessageSegment(
                                                type_=cq_data["type"], data=cq_data["data"]
                                            )
                                        )
                                    else:
                                        if previous_was_cq:
                                            convert_msg_segments = (
                                                convert_msg_segments
                                                + MessageSegment.text("\u200B")
                                            )
                                        convert_msg_segments = (
                                            convert_msg_segments
                                            + MessageSegment.text(
                                                ("\n" if (count != 0 and i == 0) else "")
                                                + part
                                            )
                                        )
                                except Exception:
                                    if previous_was_cq:
                                        convert_msg_segments = (
                                            convert_msg_segments
                                            + MessageSegment.text("\u200B")
                                        )
                                    convert_msg_segments = (
                                        convert_msg_segments
                                        + MessageSegment.text(
                                            ("\n" if (count != 0 and i == 0) else "") + part
                                        )
                                    )
                                finally:
                                    previous_was_cq = True
                            else:
                                convert_msg_segments = (
                                    convert_msg_segments
                                    + MessageSegment.text(
                                        ("\n" if count != 0 else "") + part
                                    )
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
                elif isinstance(x, VoiceElement):
                    convert_msg_segments = convert_msg_segments + MessageSegment.record(
                        file=Path(x.path).as_uri()
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Voice: {str(x)}")
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
                    img_chain = message.copy()
                    img_chain.insert(0, I18NContext("error.message.limited.msg2img"))
                    imgs = await msgchain2image(img_chain, session_info)
                    msgsgm = MessageSegment.text("")
                    if imgs:
                        for img in imgs:
                            msgsgm = msgsgm + MessageSegment.image(
                                "base64://" + await img.get_base64()
                            )
                        try:
                            send = await aiocqhttp_bot.send_group_msg(
                                group_id=int(session_info.get_common_target_id()), message=msgsgm
                            )
                        except aiocqhttp.exceptions.ActionFailed:
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
    async def delete_message(cls, session_info: SessionInfo, message_id: str | list[str]) -> None:
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
                    await aiocqhttp_bot.call_action("set_msg_emoji_like",
                                                    message_id=message_id[-1],
                                                    emoji_id=emoji,
                                                    set=True)
                elif obi == "lagrange":
                    await aiocqhttp_bot.call_action("set_group_reaction",
                                                    group_id=int(session_info.get_common_target_id()),
                                                    message_id=message_id[-1],
                                                    code=emoji,
                                                    is_add=True)
                else:
                    pass
                Logger.info(f"Added reaction \"{emoji}\" to message {message_id} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to add reaction \"{emoji}\" to message {
                                 message_id} in session {session_info.session_id}: ")

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
                    await aiocqhttp_bot.call_action("set_msg_emoji_like",
                                                    message_id=message_id[-1],
                                                    emoji_id=emoji,
                                                    set=False)
                elif obi == "lagrange":
                    await aiocqhttp_bot.call_action("set_group_reaction",
                                                    group_id=int(session_info.get_common_target_id()),
                                                    message_id=message_id[-1],
                                                    code=emoji,
                                                    is_add=False)
                else:
                    pass
                Logger.info(f"Removed reaction \"{emoji}\" to message {
                            message_id} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to remove reaction \"{emoji}\" to message {
                                 message_id} in session {session_info.session_id}: ")

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        async def _typing():
            if session_info.session_id not in cls.context:
                raise ValueError("Session not found in context")
            # 这里可以添加开始输入状态的逻辑
            Logger.debug(f"Start typing in session: {session_info.session_id}")

            if session_info.target_from == target_group_prefix:  # wtf onebot 11
                obi = Temp.data.get("onebot_impl")
                if obi in ["llonebot", "napcat"]:
                    await aiocqhttp_bot.call_action(
                        "set_msg_emoji_like",
                        message_id=session_info.message_id,
                        emoji_id=qq_typing_emoji,
                        set=True)
                elif obi == "lagrange":
                    await aiocqhttp_bot.call_action(
                        "set_group_reaction",
                        group_id=int(session_info.get_common_target_id()),
                        message_id=session_info.message_id,
                        code=qq_typing_emoji,
                        is_add=True)
                else:
                    if session_info.sender_id in last_send_typing_time:
                        if time.time() - last_send_typing_time[session_info.sender_id] <= 3600:
                            return
                    last_send_typing_time[session_info.sender_id] = time.time()
                    if obi == "shamrock":
                        await aiocqhttp_bot.send_group_msg(
                            group_id=int(session_info.get_common_target_id()),
                            message=f"[CQ:touch,id={session_info.get_common_sender_id()}]")
                    elif obi == "go-cqhttp":
                        await aiocqhttp_bot.send_group_msg(
                            group_id=int(session_info.get_common_target_id()),
                            message=f"[CQ:poke,qq={session_info.get_common_sender_id()}]")
                    else:
                        pass
            flag = asyncio.Event()
            cls.typing_flags[session_info.session_id] = flag
            await flag.wait()

        asyncio.create_task(_typing())

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        if session_info.session_id in cls.typing_flags:
            cls.typing_flags[session_info.session_id].set()
            del cls.typing_flags[session_info.session_id]
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
                await aiocqhttp_bot.call_action("set_msg_emoji_like",
                                                message_id=session_info.message_id,
                                                emoji_id=qq_limited_emoji,
                                                set=True)
            elif obi == "lagrange":
                await aiocqhttp_bot.call_action("set_group_reaction",
                                                group_id=int(session_info.get_common_target_id()),
                                                message_id=session_info.message_id,
                                                code=qq_limited_emoji,
                                                is_add=True)
            elif obi == "shamrock":
                await aiocqhttp_bot.call_action("send_group_msg",
                                                group_id=int(session_info.get_common_target_id()),
                                                message=f"[CQ:touch,id={qq_account}]")
            elif obi == "go-cqhttp":
                await aiocqhttp_bot.call_action("send_group_msg",
                                                group_id=int(session_info.get_common_target_id()),
                                                message=f"[CQ:poke,qq={qq_account}]")
            else:
                pass

    @classmethod
    async def call_onebot_api(cls, api_name: str, **kwargs) -> dict | None:
        return await aiocqhttp_bot.call_action(api_name, **kwargs)


_tasks_high_priority = []
_tasks = []


class AIOCQFetchedContextManager(AIOCQContextManager):

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: MessageChain | MessageNodes,
                           quote: bool = True,
                           enable_parse_message=True,
                           enable_split_image=True) -> None:
        append_tsk = _tasks_high_priority if session_info.target_info.target_data.get(
            "in_post_whitelist", False) else _tasks
        append_tsk.append(
            super().send_message(
                session_info,
                message,
                quote=quote,
                enable_parse_message=enable_parse_message,
            ))

    @staticmethod
    async def process_tasks():
        while True:
            if _tasks_high_priority:
                task = _tasks_high_priority.pop(0)
                await task
                cd = random.randint(1, 5)
                Logger.info(f"Processed a high-priority task in AIOCQFetchedContextManager, waiting cooldown for {
                    cd}s...")
                await asyncio.sleep(cd)
            elif _tasks:
                task = _tasks.pop(0)
                await task
                cd = random.randint(5, qq_initiative_msg_cooldown)
                Logger.info(f"Processed a task in AIOCQFetchedContextManager, waiting cooldown for {
                    cd}s...")
                await asyncio.sleep(cd)
            else:
                await asyncio.sleep(1)
