import asyncio
import datetime
import html
import random
import re
import traceback
from pathlib import Path
from typing import List, Union, Optional

import aiocqhttp.exceptions
from aiocqhttp import MessageSegment
from tenacity import retry, wait_fixed, stop_after_attempt

from bots.aiocqhttp.client import bot
from bots.aiocqhttp.info import *
from bots.aiocqhttp.utils import CQCodeHandler, get_onebot_implementation
from core.builtins import (
    Bot,
    base_superuser_list,
    command_prefix,
    I18NContext,
    Temp,
    MessageTaskManager,
    FetchTarget as FetchTargetT,
    FinishedSession as FinishedSessionT,
    Mention,
    Plain,
    Image,
    Voice,
)
from core.builtins.message import MessageSession as MessageSessionT
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import MentionElement, PlainElement, ImageElement, VoiceElement
from core.config import Config
from core.constants.exceptions import SendMessageFailed
from core.database.models import AnalyticsData, TargetInfo
from core.logger import Logger
from core.utils.image import msgchain2image
from core.utils.storedata import get_stored_list

enable_analytics = Config("enable_analytics", False)
qq_typing_emoji = str(Config("qq_typing_emoji", 181, (str, int), table_name="bot_aiocqhttp"))


class FinishedSession(FinishedSessionT):
    async def delete(self):
        if self.session.target.target_from in [
            target_group_prefix,
            target_private_prefix,
        ]:
            try:
                for x in self.message_id:
                    if x != 0:
                        await bot.call_action("delete_msg", message_id=x)
            except Exception:
                Logger.error(traceback.format_exc())


last_send_typing_time = {}
Temp.data["is_group_message_blocked"] = False
Temp.data["waiting_for_send_group_message"] = []
group_info = {}


async def resending_group_message():
    falied_list = []
    try:
        if targets := Temp.data["waiting_for_send_group_message"]:
            for x in targets:
                try:
                    if x["i18n"]:
                        await x["fetch"].send_direct_message(I18NContext(x["message"], **x["kwargs"]))
                    else:
                        await x["fetch"].send_direct_message(x["message"])
                    Temp.data["waiting_for_send_group_message"].remove(x)
                    await asyncio.sleep(30)
                except SendMessageFailed:
                    Logger.error(traceback.format_exc())
                    falied_list.append(x)
                    if len(falied_list) > 3:
                        raise SendMessageFailed
        Temp.data["is_group_message_blocked"] = False
    except SendMessageFailed:
        Logger.error(traceback.format_exc())
        Temp.data["is_group_message_blocked"] = True
        for bu in base_superuser_list:
            fetch_base_superuser = await FetchTarget.fetch_target(bu)
            if fetch_base_superuser:
                await fetch_base_superuser.send_direct_message(
                    I18NContext("error.message.paused", disable_joke=True, prefix=command_prefix[0])
                )


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = True
        mention = True
        embed = False
        forward = True
        delete = True
        markdown = False
        quote = True
        rss = True
        typing = True
        wait = True

    async def send_message(
        self,
        message_chain,
        quote=True,
        disable_secret_check=False,
        enable_parse_message=True,
        enable_split_image=True,
        callback=None,
    ) -> FinishedSession:

        send = None
        message_chain = MessageChain(message_chain)
        message_chain_assendable = message_chain.as_sendable(self, embed=False)

        convert_msg_segments = MessageSegment.text("")
        if (
            quote
            and self.target.target_from == target_group_prefix
            and self.session.message
        ):
            convert_msg_segments = MessageSegment.reply(self.session.message.message_id)

        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message([I18NContext("error.message.chain.unsafe")])
        self.sent.append(message_chain)
        count = 0
        for x in message_chain_assendable:
            if isinstance(x, PlainElement):
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
                count += 1
            elif isinstance(x, ImageElement):
                convert_msg_segments = convert_msg_segments + MessageSegment.image(
                    "base64://" + await x.get_base64()
                )
                count += 1
            elif isinstance(x, VoiceElement):
                if self.target.target_from != target_guild_prefix:
                    convert_msg_segments = convert_msg_segments + MessageSegment.record(
                        file=Path(x.path).as_uri()
                    )
                    count += 1
            elif isinstance(x, MentionElement):
                if x.client == client_name and self.target.target_from == target_group_prefix:
                    convert_msg_segments = convert_msg_segments + MessageSegment.at(x.id)
                else:
                    convert_msg_segments = convert_msg_segments + MessageSegment.text(" ")
                count += 1

        Logger.info(f"[Bot] -> [{self.target.target_id}]: {message_chain_assendable}")
        if self.target.target_from == target_group_prefix:
            try:
                send = await bot.send_group_msg(
                    group_id=self.session.target, message=convert_msg_segments
                )
            except aiocqhttp.exceptions.NetworkError:
                send = await bot.send_group_msg(
                    group_id=self.session.target,
                    message=MessageSegment.text(self.locale.t("error.message.timeout")),
                )
            except aiocqhttp.exceptions.ActionFailed:
                img_chain = message_chain.copy()
                img_chain.insert(0, I18NContext("error.message.limited.msg2img"))
                imgs = await msgchain2image(img_chain, self)
                msgsgm = MessageSegment.text("")
                if imgs:
                    for img in imgs:
                        im = Image(img)
                        msgsgm = msgsgm + MessageSegment.image(
                            "base64://" + await im.get_base64()
                        )
                    try:
                        send = await bot.send_group_msg(
                            group_id=self.session.target, message=msgsgm
                        )
                    except aiocqhttp.exceptions.ActionFailed as e:
                        raise SendMessageFailed(e.result["wording"])

            if Temp.data["is_group_message_blocked"]:
                asyncio.create_task(resending_group_message())

        elif self.target.target_from == target_guild_prefix:
            match_guild = re.match(r"(.*)\|(.*)", self.session.target)
            send = await bot.call_action(
                "send_guild_channel_msg",
                guild_id=int(match_guild.group(1)),
                channel_id=int(match_guild.group(2)),
                message=convert_msg_segments,
            )
        else:
            try:
                send = await bot.send_private_msg(
                    user_id=self.session.target, message=convert_msg_segments
                )
            except aiocqhttp.exceptions.ActionFailed as e:
                if (
                    self.session.message.detail_type == "private"
                    and self.session.message.sub_type == "group"
                ):
                    return FinishedSession(self, 0, [{}])
                raise e
        if send:
            if callback:
                MessageTaskManager.add_callback(send["message_id"], callback)
            return FinishedSession(self, send["message_id"], [send])

    async def check_native_permission(self):
        @retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
        async def _check():
            if self.target.target_from == target_private_prefix:
                return True
            if self.target.target_from == target_group_prefix:
                get_member_info = await bot.call_action(
                    "get_group_member_info",
                    group_id=self.session.target,
                    user_id=self.session.sender,
                )
                if get_member_info["role"] in ["owner", "admin"]:
                    return True
            elif self.target.target_from == target_guild_prefix:
                match_guild = re.match(r"(.*)\|(.*)", self.session.target)
                get_member_info = await bot.call_action(
                    "get_guild_member_profile",
                    guild_id=match_guild.group(1),
                    user_id=self.session.sender,
                )
                for m in get_member_info["roles"]:
                    if m["role_id"] == "2":
                        return True
                get_guild_info = await bot.call_action(
                    "get_guild_meta_by_guest", guild_id=match_guild.group(1)
                )
                if get_guild_info["owner_id"] == self.session.sender:
                    return True
                return False
            return False

        return await _check()

    def as_display(self, text_only=False):
        if isinstance(self.session.message.message, str):

            m = html.unescape(self.session.message.message)
            if text_only:
                m = re.sub(r"\[CQ:text,qq=(.*?)]", r"\1", m)
                m = CQCodeHandler.pattern.sub("", m)
            else:
                m = CQCodeHandler.filter_cq(m)
                m = re.sub(r"\[CQ:at,qq=(.*?)]", rf"{sender_prefix}|\1", m)
                m = re.sub(r"\[CQ:json,data=(.*?)]", r"\1", m).replace("\\/", "/")
                m = re.sub(r"\[CQ:text,qq=(.*?)]", r"\1", m)
            return m.strip()
        m = []
        for item in self.session.message.message:
            if text_only:
                if item["type"] == "text":
                    m.append(item["data"]["text"])
            else:
                if item["type"] == "at":
                    m.append(rf"{sender_prefix}|{item["data"]["qq"]}")
                elif item["type"] == "json":
                    m.append(
                        html.unescape(str(item["data"]["data"])).replace("\\/", "/")
                    )
                elif item["type"] == "text":
                    m.append(item["data"]["text"])
                elif item["type"] in CQCodeHandler.get_supported:
                    m.append(CQCodeHandler.generate_cq(item))

        return "".join(m).strip()

    async def fake_forward_msg(self, nodelist):
        if self.target.target_from == target_group_prefix:
            get_ = await get_stored_list(Bot.FetchTarget, "forward_msg")
            if isinstance(get_[0], dict) and get_[0].get("status"):
                await self.send_message(I18NContext("core.message.forward_msg.disabled"))
                raise ValueError
            await bot.call_action(
                "send_group_forward_msg",
                group_id=int(self.session.target),
                messages=nodelist,
            )
        elif self.target.target_from == target_private_prefix:
            await bot.call_action(
                "send_private_forward_msg",
                user_id=int(self.target.sender_id.split("|")[1]),
                messages=nodelist
            )

    async def msgchain2nodelist(
        self,
        msg_chain_list: List[MessageChain],
        sender_name: Optional[str] = None,
    ) -> List[dict]:
        node_list = []
        for message in msg_chain_list:
            content = ""
            msgchain = message.as_sendable()
            for x in msgchain:
                if isinstance(x, PlainElement):
                    content += x.text + "\n"
                elif isinstance(x, ImageElement):
                    content += f"[CQ:image,file=base64://{x.get_base64()}]\n"

            template = {
                "type": "node",
                "data": {
                    "nickname": sender_name if sender_name else Temp().data.get("qq_nickname"),
                    "user_id": str(Temp().data.get("qq_account")),
                    "content": content.strip()
                }
            }
            node_list.append(template)
        return node_list

    async def delete(self):
        if self.target.target_from in [target_private_prefix, target_group_prefix]:
            try:
                if isinstance(self.session.message, list):
                    for x in self.session.message:
                        await bot.call_action("delete_msg", message_id=x["message_id"])
                else:
                    await bot.call_action(
                        "delete_msg", message_id=self.session.message["message_id"]
                    )
                return True
            except Exception:
                Logger.error(traceback.format_exc())
                return False

    async def get_text_channel_list(self):
        match_guild = re.match(r"(.*)\|(.*)", self.session.target)
        get_channels_info = await bot.call_action(
            "get_guild_channel_list", guild_id=match_guild.group(1), no_cache=True
        )
        lst = []
        for m in get_channels_info:
            if m["channel_type"] == 1:
                lst.append(f"{m["owner_guild_id"]}|{m["channel_id"]}")
        return lst

    async def to_message_chain(self):
        lst = []
        if isinstance(self.session.message.message, str):
            spl = re.split(
                r"(\[CQ:(?:text|image|record|at).*?])", self.session.message.message
            )
            for s in spl:
                if not s:
                    continue
                if re.match(r"\[CQ:[^\]]+\]", s):
                    cq_data = CQCodeHandler.parse_cq(s)
                    if cq_data:
                        if cq_data["type"] == "text":
                            lst.append(Plain(cq_data["data"].get("text")))
                        elif cq_data["type"] == "image":
                            obi = await get_onebot_implementation()
                            if obi == "lagrange":
                                img_src = cq_data["data"].get("file")
                            else:
                                img_src = cq_data["data"].get("url")
                            if img_src:
                                lst.append(Image(img_src))
                        elif cq_data["type"] == "record":
                            lst.append(Voice(cq_data["data"].get("file")))
                        elif cq_data["type"] == "at":
                            lst.append(Mention(f"{sender_prefix}|{cq_data["data"].get("qq")}"))
                        else:
                            lst.append(Plain(s))
                    else:
                        lst.append(Plain(s))
                else:
                    lst.append(Plain(s))
        else:
            for item in self.session.message.message:
                if item["type"] == "text":
                    lst.append(Plain(item["data"]["text"]))
                elif item["type"] == "image":
                    obi = await get_onebot_implementation()
                    if obi == "lagrange":
                        lst.append(Image(item["data"]["file"]))
                    else:
                        lst.append(Image(item["data"]["url"]))
                elif item["type"] == "record":
                    lst.append(Voice(item["data"]["file"]))
                elif item["type"] == "at":
                    lst.append(Mention(f"{sender_prefix}|{item["data"].get("qq")}"))
                else:
                    lst.append(Plain(CQCodeHandler.generate_cq(item)))

        return MessageChain(lst)

    async def call_api(self, action, **params):
        return await bot.call_action(action, **params)

    sendMessage = send_message
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkNativePermission = check_native_permission

    class Typing:
        def __init__(self, msg: MessageSessionT):
            self.msg = msg

        async def __aenter__(self):
            if self.msg.target.target_from == target_group_prefix:  # wtf onebot 11
                obi = await get_onebot_implementation()
                if obi in ["llonebot", "napcat"]:
                    await bot.call_action(
                        "set_msg_emoji_like",
                        message_id=self.msg.session.message.message_id,
                        emoji_id=qq_typing_emoji)
                elif obi == "lagrange":
                    await bot.call_action(
                        "set_group_reaction",
                        group_id=self.msg.session.target,
                        message_id=self.msg.session.message.message_id,
                        code=qq_typing_emoji,
                        is_add=True)
                else:
                    if self.msg.session.sender in last_send_typing_time:
                        if datetime.datetime.now().timestamp() - last_send_typing_time[self.msg.session.sender] <= 3600:
                            return
                    last_send_typing_time[self.msg.session.sender] = datetime.datetime.now().timestamp()
                    if obi == "shamrock":
                        await bot.send_group_msg(
                            group_id=self.msg.session.target,
                            message=f"[CQ:touch,id={self.msg.session.sender}]")
                    elif obi == "go-cqhttp":
                        await bot.send_group_msg(
                            group_id=self.msg.session.target,
                            message=f"[CQ:poke,qq={self.msg.session.sender}]")
                    else:
                        pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        target_pattern = r"|".join(re.escape(item) for item in target_prefix_list)
        match_target = re.match(rf"({target_pattern})\|(.*)", target_id)
        if match_target:
            target_from = sender_from = match_target.group(1)
            target_id = match_target.group(2)
            if sender_id:
                sender_pattern = r"|".join(
                    re.escape(item) for item in sender_prefix_list
                )
                match_sender = re.match(rf"^({sender_pattern})\|(.*)", sender_id)
                if match_sender:
                    sender_from = match_sender.group(1)
                    sender_id = match_sender.group(2)
            else:
                sender_id = target_id
            session = Bot.FetchedSession(target_from, target_id, sender_from, sender_id)
            await session.parent.data_init()
            return session

    @staticmethod
    async def fetch_target_list(target_list) -> List[Bot.FetchedSession]:
        lst = []
        group_list_raw = await bot.call_action("get_group_list")
        group_list = []
        for g in group_list_raw:
            group_list.append(g["group_id"])
        friend_list_raw = await bot.call_action("get_friend_list")
        friend_list = []
        guild_list_raw = await bot.call_action("get_guild_list")
        guild_list = []
        for g in guild_list_raw:
            get_channel_list = await bot.call_action(
                "get_guild_channel_list", guild_id=g["guild_id"]
            )
            for channel in get_channel_list:
                if channel["channel_type"] == 1:
                    guild_list.append(
                        f"{str(g["guild_id"])}|{str(channel["channel_id"])}"
                    )
        for f in friend_list_raw:
            friend_list.append(f)
        for x in target_list:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                if fet.target.target_from == target_group_prefix:
                    if fet.session.target not in group_list:
                        continue
                if fet.target.target_from == target_private_prefix:
                    if fet.session.target not in friend_list:
                        continue
                if fet.target.target_from == target_guild_prefix:
                    if fet.session.target not in guild_list:
                        continue
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list=None, i18n=False, **kwargs):
        _tsk = []
        blocked = False
        module_name = None if module_name == "*" else module_name

        async def post_(fetch_: Bot.FetchedSession):
            nonlocal _tsk
            nonlocal blocked
            try:
                if (
                    Temp.data["is_group_message_blocked"]
                    and fetch_.target.target_from == target_group_prefix
                ):
                    Temp.data["waiting_for_send_group_message"].append(
                        {
                            "fetch": fetch_,
                            "message": message,
                            "i18n": i18n,
                            "kwargs": kwargs,
                        }
                    )
                else:
                    msgchain = message
                    if isinstance(message, str):
                        if i18n:
                            msgchain = MessageChain([I18NContext(message, **kwargs)])
                        else:
                            msgchain = MessageChain([Plain(message)])
                    msgchain = MessageChain(msgchain)
                    new_msgchain = []
                    for v in msgchain.value:
                        if isinstance(v, ImageElement):
                            new_msgchain.append(await v.add_random_noise())
                        else:
                            new_msgchain.append(v)
                    await fetch_.send_direct_message(new_msgchain)
                    if _tsk:
                        _tsk = []
                if enable_analytics and module_name:
                    await AnalyticsData.create(target_id=fetch_.target.target_id,
                                               sender_id=fetch_.target.sender_id,
                                               command="",
                                               module_name=module_name,
                                               module_type="schedule")
                await asyncio.sleep(0.5)
            except SendMessageFailed as e:
                if str(e).startswith("send group message failed: blocked by server"):
                    if len(_tsk) >= 3:
                        blocked = True
                    if not blocked:
                        _tsk.append(
                            {
                                "fetch": fetch_,
                                "message": message,
                                "i18n": i18n,
                                "kwargs": kwargs,
                            }
                        )
                    else:
                        Temp.data["is_group_message_blocked"] = True
                        Temp.data["waiting_for_send_group_message"].append(
                            {
                                "fetch": fetch_,
                                "message": message,
                                "i18n": i18n,
                                "kwargs": kwargs,
                            }
                        )
                        if _tsk:
                            for t in _tsk:
                                Temp.data["waiting_for_send_group_message"].append(t)
                            _tsk = []
                        for bu in base_superuser_list:
                            fetch_base_superuser = await FetchTarget.fetch_target(bu)
                            if fetch_base_superuser:
                                await fetch_base_superuser.send_direct_message(
                                    I18NContext("error.message.paused", disable_joke=True, prefix=command_prefix[0])
                                )
            except Exception:
                Logger.error(traceback.format_exc())

        if user_list:
            for x in user_list:
                await post_(x)
        else:
            get_target_id = await TargetInfo.get_target_list_by_module(
                module_name, client_name
            )
            group_list_raw = await bot.call_action("get_group_list")
            group_list = [g["group_id"] for g in group_list_raw]
            friend_list_raw = await bot.call_action("get_friend_list")
            friend_list = [f["user_id"] for f in friend_list_raw]

            guild_list = []
            obi = await get_onebot_implementation()
            if obi == "go-cqhttp":
                guild_list_raw = await bot.call_action("get_guild_list")
                for g in guild_list_raw:
                    try:
                        get_channel_list = await bot.call_action(
                            "get_guild_channel_list",
                            guild_id=g["guild_id"],
                            no_cache=True,
                        )
                        for channel in get_channel_list:
                            if channel["channel_type"] == 1:
                                guild_list.append(
                                    f"{str(g["guild_id"])}|{str(channel["channel_id"])}"
                                )
                    except Exception:
                        traceback.print_exc()
                        continue

            in_whitelist = []
            else_ = []
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x.target_id)
                Logger.debug(fetch)
                if fetch:
                    if fetch.target.target_from == target_group_prefix:
                        if int(fetch.session.target) not in group_list:
                            continue
                    if fetch.target.target_from == target_private_prefix:
                        if int(fetch.session.target) not in friend_list:
                            continue
                    if fetch.target.target_from == target_guild_prefix:
                        if fetch.session.target not in guild_list:
                            continue
                    if x.muted:
                        continue

                    if fetch.target.target_from in [
                        target_private_prefix,
                        target_guild_prefix,
                    ]:
                        in_whitelist.append(post_(fetch))
                    else:
                        load_options: dict = x.target_data
                        if load_options.get("in_post_whitelist", False):
                            in_whitelist.append(post_(fetch))
                        else:
                            else_.append(post_(fetch))

            async def post_in_whitelist(lst):
                for f in lst:
                    await f
                    await asyncio.sleep(random.randint(1, 5))

            if in_whitelist:
                asyncio.create_task(post_in_whitelist(in_whitelist))

            async def post_not_in_whitelist(lst):
                for f in lst:
                    await f
                    await asyncio.sleep(random.randint(15, 30))

            if else_:
                asyncio.create_task(post_not_in_whitelist(else_))
                Logger.info(
                    f"The task of posting messages to whitelisted groups is complete. "
                    f"Posting message to {len(else_)} groups not in whitelist."
                )


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
