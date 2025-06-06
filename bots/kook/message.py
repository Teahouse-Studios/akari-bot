import re
from typing import Union

import httpx
import orjson as json
from khl import MessageTypes, Message

from core.builtins import (
    Bot,
    Plain,
    Image,
    Voice,
    I18NContext,
    MessageTaskManager,
    MessageSession as MessageSessionT,
    FetchTarget as FetchTargetT,
    FinishedSession as FinishedSessionT
)
from core.builtins.message.chain import MessageChain, match_atcode
from core.builtins.message.elements import MentionElement, PlainElement, ImageElement, VoiceElement
from core.config import Config
from core.logger import Logger
from .client import bot
from .info import *

kook_base = "https://www.kookapp.cn"
kook_token = Config("kook_token", cfg_type=str, secret=True, table_name="bot_kook")
kook_headers = {
    "Authorization": f"Bot {kook_token}"
}


async def direct_msg_delete(msg_id: str):
    """删除私聊消息"""
    url = f"{kook_base}/api/v3/direct-message/delete"
    params = {"msg_id": msg_id}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=params, headers=kook_headers)
    return json.loads(resp.text)


async def channel_msg_delete(msg_id: str):
    """删除普通消息"""
    url = f"{kook_base}/api/v3/message/delete"
    params = {"msg_id": msg_id}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=params, headers=kook_headers)
    return json.loads(resp.text)


class FinishedSession(FinishedSessionT):
    async def delete(self):
        try:
            for x in self.result:
                for y in self.result[x]:
                    if x == "PERSON":
                        await direct_msg_delete(y["msg_id"])
                    else:
                        await channel_msg_delete(y["msg_id"])
        except Exception:
            Logger.exception()


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = True
        mention = True
        embed = False
        forward = False
        delete = True
        markdown = True
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
        self.session.message: Message
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(I18NContext("error.message.chain.unsafe"))
        self.sent.append(message_chain)
        count = 0
        send = []
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, PlainElement):
                x.text = match_atcode(x.text, client_name, "(met){uid}(met)")
                send_ = await self.session.message.reply(
                    x.text,
                    quote=(
                        quote if quote and count == 0 and self.session.message else None
                    ),
                )

                Logger.info(f"[Bot] -> [{self.target.target_id}]: {x.text}")
                send.append(send_)
                count += 1
            elif isinstance(x, ImageElement):
                url = await bot.create_asset(open(await x.get(), "rb"))
                send_ = await self.session.message.reply(
                    url,
                    type=MessageTypes.IMG,
                    quote=(
                        quote if quote and count == 0 and self.session.message else None
                    ),
                )
                Logger.info(
                    f"[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}"
                )
                send.append(send_)
                count += 1
            elif isinstance(x, VoiceElement):
                url = await bot.create_asset(open(x.path, "rb"))
                send_ = await self.session.message.reply(
                    url,
                    type=MessageTypes.AUDIO,
                    quote=(
                        quote if quote and count == 0 and self.session.message else None
                    ),
                )
                Logger.info(
                    f"[Bot] -> [{self.target.target_id}]: Voice: {str(x.__dict__)}"
                )
                send.append(send_)
                count += 1
            elif isinstance(x, MentionElement):
                if x.client == client_name and self.target.target_from == target_group_prefix:
                    send_ = await self.session.message.reply(
                        f"(met){x.id}(met)",
                        quote=(
                            quote if quote and count == 0 and self.session.message else None
                        ),
                    )
                    Logger.info(
                        f"[Bot] -> [{self.target.target_id}]: Mention: {sender_prefix}|{str(x.id)}"
                    )
                    send.append(send_)
                    count += 1
        msg_ids = []
        for x in send:
            msg_ids.append(x["msg_id"])
            if callback:
                MessageTaskManager.add_callback(x["msg_id"], callback)
        return FinishedSession(
            self, msg_ids, {self.session.message.channel_type.name.title(): send}
        )

    async def check_native_permission(self):
        self.session.message: Message
        if not self.session.message:
            channel = await bot.client.fetch_public_channel(self.session.target)
            author = self.session.sender
        else:
            channel = await bot.client.fetch_public_channel(
                self.session.message.ctx.channel.id
            )
            author = self.session.message.author.id
        if channel.name == "PERSON":
            return True
        guild = await bot.client.fetch_guild(channel.guild_id)
        user_roles = (await guild.fetch_user(author)).roles
        guild_roles = await guild.fetch_roles()
        for i in guild_roles:  # 遍历服务器身分组
            if i.id in user_roles and i.has_permission(0):
                return True
        if author == guild.master_id:
            return True
        return False

    def as_display(self, text_only=False):
        if self.session.message.content:
            m = re.sub(r"\[.*\]\((.*)\)", r"\1", self.session.message.content)
            return m
        return ""

    async def to_message_chain(self):
        lst = []
        if self.session.message.type == MessageTypes.TEXT:
            lst.append(Plain(self.session.message.content))
        elif self.session.message.type == MessageTypes.IMG:
            lst.append(Image(self.session.message.content))
        elif self.session.message.type == MessageTypes.AUDIO:
            lst.append(Voice(self.session.message.content))
        return MessageChain(lst)

    async def delete(self):
        self.session.message: Message
        try:
            if self.session.message.channel_type.name == "PERSON":
                await direct_msg_delete(self.session.message.id)
            else:
                await channel_msg_delete(self.session.message.id)
            return True
        except Exception:
            Logger.exception()
            return False

    sendMessage = send_message
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkNativePermission = check_native_permission

    class Typing:
        def __init__(self, msg: MessageSessionT):
            self.msg = msg

        async def __aenter__(self):
            # await bot.answer_chat_action(self.msg.session.target, "typing")
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(Bot.FetchedSession):

    async def send_direct_message(
        self,
        message_chain,
        disable_secret_check=False,
        enable_parse_message=True,
        enable_split_image=True,
    ):
        if self.target.target_from == target_group_prefix:
            get_channel = await bot.client.fetch_public_channel(self.session.target)
            if not get_channel:
                return False
        elif self.target.target_from == target_person_prefix:
            get_channel = await bot.client.fetch_user(self.session.target)
            Logger.debug(f"get_channel: {get_channel}")
            if not get_channel:
                return False
        else:
            return False

        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            await self.send_direct_message(I18NContext("error.message.chain.unsafe"))
        for x in message_chain.as_sendable(self.parent, embed=False):
            if isinstance(x, PlainElement):
                await get_channel.send(x.text)

                Logger.info(f"[Bot] -> [{self.target.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                url = await bot.create_asset(open(await x.get(), "rb"))
                await get_channel.send(url, type=MessageTypes.IMG)
                Logger.info(
                    f"[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}"
                )
            elif isinstance(x, VoiceElement):
                url = await bot.create_asset(open(x.path, "rb"))
                await get_channel.send(url, type=MessageTypes.AUDIO)
                Logger.info(
                    f"[Bot] -> [{self.target.target_id}]: Voice: {str(x.__dict__)}"
                )


Bot.FetchedSession = FetchedSession


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        target_pattern = r"|".join(re.escape(item) for item in target_prefix_list)
        match_target = re.match(rf"^({target_pattern})\|(.*)", target_id)
        if match_target:
            target_from = match_target.group(1)
            target_id = match_target.group(2)
            sender_from = None
            if sender_id:
                sender_pattern = r"|".join(
                    re.escape(item) for item in sender_prefix_list
                )
                match_sender = re.match(rf"^({sender_pattern})\|(.*)", sender_id)
                if match_sender:
                    sender_from = match_sender.group(1)
                    sender_id = match_sender.group(2)
            session = Bot.FetchedSession(target_from, target_id, sender_from, sender_id)
            await session.parent.data_init()
            return session


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
