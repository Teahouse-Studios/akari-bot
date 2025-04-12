import re
import traceback
from typing import List, Union

import filetype
from botpy.message import C2CMessage, DirectMessage, GroupMessage, Message
from botpy.errors import ServerError
from botpy.types.message import Reference

from bots.qqbot.info import *
from core.builtins import (
    Bot,
    Plain,
    Image,
    MessageSession as MessageSessionT,
    I18NContext,
    Url,
    MessageTaskManager,
    FetchTarget as FetchTargetT,
    FinishedSession as FinishedSessionT,
)
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement, MentionElement
from core.config import Config
from core.database.models import AnalyticsData, TargetInfo
from core.logger import Logger
from core.utils.http import download, url_pattern
from core.utils.image import msgchain2image


enable_analytics = Config("enable_analytics", False)
enable_send_url = Config("qq_bot_enable_send_url", False, table_name="bot_qqbot")


class FinishedSession(FinishedSessionT):
    async def delete(self):
        try:
            from bots.qqbot.bot import client  # noqa

            if self.session.target.target_from == target_guild_prefix:
                for x in self.message_id:
                    await client.api.recall_message(
                        channel_id=self.session.target.target_id.split("|")[-1],
                        message_id=x,
                        hidetip=True,
                    )
            elif self.session.target.target_from == target_group_prefix:
                for x in self.message_id:
                    await client.api.recall_group_message(
                        group_openid=self.session.target.target_id.split("|")[-1],
                        message_id=x,
                    )
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = False
        mention = True
        embed = False
        forward = False
        delete = True
        markdown = False
        quote = True
        rss = False
        typing = False
        wait = False

    async def send_message(
        self,
        message_chain,
        quote=False,
        disable_secret_check=False,
        enable_parse_message=False,
        enable_split_image=False,
        callback=None,
    ) -> FinishedSession:
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(I18NContext("error.message.chain.unsafe"))

        plains: List[PlainElement] = []
        images: List[ImageElement] = []

        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, PlainElement):
                plains.append(x)
            elif isinstance(x, ImageElement):
                images.append(x)
            elif isinstance(x, MentionElement):
                if x.client == client_name and self.target.target_from == target_guild_prefix:
                    plains.append(PlainElement(text=f"<@{x.id}>"))
        sends = []
        if len(plains + images) != 0:
            msg = "\n".join([x.text for x in plains]).strip()

            filtered_msg = []
            lines = msg.split("\n")
            for line in lines:
                if enable_send_url:
                    line = url_pattern.sub(
                        lambda match: str(Url(match.group(0), use_mm=True)), line
                    )
                elif url_pattern.findall(line):
                    continue
                filtered_msg.append(line)
            msg = "\n".join(filtered_msg).strip()
            image_1 = None
            send_img = None
            sends = []
            if isinstance(self.session.message, Message):
                if images:
                    image_1 = images[0]
                    images.pop(0)
                send_img = await image_1.get() if image_1 else None
                msg_quote = (
                    Reference(
                        message_id=self.session.message.id,
                        ignore_get_message_error=False,
                    )
                    if quote and not send_img
                    else None
                )
                if not msg_quote and quote:
                    msg = f"<@{self.session.message.author.id}> \n" + msg
                msg = "" if not msg else msg
                send = await self.session.message.reply(
                    content=msg, file_image=send_img, message_reference=msg_quote
                )
                Logger.info(f"[Bot] -> [{self.target.target_id}]: {msg}")
                if image_1:
                    Logger.info(
                        f"[Bot] -> [{self.target.target_id}]: Image: {str(image_1.__dict__)}"
                    )
                if images:
                    for img in images:
                        send_img = await img.get()
                        send = await self.session.message.reply(file_image=send_img)
                        Logger.info(
                            f"[Bot] -> [{self.target.target_id}]: Image: {str(img.__dict__)}"
                        )
                        if send:
                            sends.append(send)
                sends.append(send)
            elif isinstance(self.session.message, DirectMessage):
                if images:
                    image_1 = images[0]
                    images.pop(0)
                send_img = await image_1.get() if image_1 else None
                msg_quote = (
                    Reference(
                        message_id=self.session.message.id,
                        ignore_get_message_error=False,
                    )
                    if quote and not send_img
                    else None
                )
                msg = "" if not msg else msg
                send = await self.session.message.reply(
                    content=msg, file_image=send_img, message_reference=msg_quote
                )
                sends.append(send)
                Logger.info(f"[Bot] -> [{self.target.target_id}]: {msg}")
                if image_1:
                    Logger.info(
                        f"[Bot] -> [{self.target.target_id}]: Image: {str(image_1.__dict__)}"
                    )
                if images:
                    for img in images:
                        send_img = await img.get()
                        send = await self.session.message.reply(file_image=send_img)
                        Logger.info(
                            f"[Bot] -> [{self.target.target_id}]: Image: {str(img.__dict__)}"
                        )
                        if send:
                            sends.append(send)
            elif isinstance(self.session.message, GroupMessage):
                seq = (
                    self.session.message.msg_seq if self.session.message.msg_seq else 1
                )
                if images:
                    image_1 = images[0]
                    images.pop(0)
                    send_img = await self.session.message._api.post_group_file(
                        group_openid=self.session.message.group_openid,
                        file_type=1,
                        file_data=await image_1.get_base64(),
                    )
                if msg and self.session.message.id:
                    msg = "\n" + msg
                msg = "" if not msg else msg
                try:
                    send = await self.session.message.reply(
                        content=msg,
                        msg_type=7 if send_img else 0,
                        media=send_img,
                        msg_seq=seq,
                    )
                    Logger.info(f"[Bot] -> [{self.target.target_id}]: {msg.strip()}")
                    if image_1:
                        Logger.info(
                            f"[Bot] -> [{self.target.target_id}]: Image: {str(image_1.__dict__)}"
                        )
                    if send:
                        sends.append(send)
                        seq += 1
                except ServerError:
                    img_chain = filtered_msg
                    img_chain.insert(0, I18NContext("error.message.limited.msg2img"))
                    if image_1:
                        img_chain.append(image_1)
                    imgs = await msgchain2image(img_chain, self)
                    if imgs:
                        imgs = [Image(img) for img in imgs]
                        images = imgs + images
                if images:
                    for img in images:
                        send_img = await self.session.message._api.post_group_file(
                            group_openid=self.session.message.group_openid,
                            file_type=1,
                            file_data=await img.get_base64(),
                        )
                        send = await self.session.message.reply(
                            msg_type=7, media=send_img, msg_seq=seq
                        )
                        Logger.info(
                            f"[Bot] -> [{self.target.target_id}]: Image: {str(img.__dict__)}"
                        )
                        if send:
                            sends.append(send)
                            seq += 1
                self.session.message.msg_seq = seq
            elif isinstance(self.session.message, C2CMessage):
                seq = (
                    self.session.message.msg_seq if self.session.message.msg_seq else 1
                )
                if images:
                    image_1 = images[0]
                    images.pop(0)
                    send_img = await self.session.message._api.post_c2c_file(
                        openid=self.session.message.author.user_openid,
                        file_type=1,
                        file_data=await image_1.get_base64(),
                    )
                msg = "" if not msg else msg
                try:
                    send = await self.session.message.reply(
                        content=msg,
                        msg_type=7 if send_img else 0,
                        media=send_img,
                        msg_seq=seq,
                    )
                    Logger.info(f"[Bot] -> [{self.target.target_id}]: {msg.strip()}")
                    if image_1:
                        Logger.info(
                            f"[Bot] -> [{self.target.target_id}]: Image: {str(image_1.__dict__)}"
                        )
                    if send:
                        sends.append(send)
                        seq += 1
                except ServerError:
                    img_chain = filtered_msg
                    img_chain.insert(0, I18NContext("error.message.limited.msg2img"))
                    if image_1:
                        img_chain.append(image_1)
                    imgs = await msgchain2image(img_chain, self)
                    if imgs:
                        imgs = [Image(img) for img in imgs]
                        images = imgs + images
                if images:
                    for img in images:
                        send_img = await self.session.message._api.post_c2c_file(
                            openid=self.session.message.author.user_openid,
                            file_type=1,
                            file_data=await img.get_base64(),
                        )
                        send = await self.session.message.reply(
                            msg_type=7, media=send_img, msg_seq=seq
                        )
                        Logger.info(
                            f"[Bot] -> [{self.target.target_id}]: Image: {str(img.__dict__)}"
                        )
                        if send:
                            sends.append(send)
                            seq += 1
                self.session.message.msg_seq = seq
        msg_ids = []
        for x in sends:
            msg_ids.append(x["id"])
            if callback:
                MessageTaskManager.add_callback(x["id"], callback)

        return FinishedSession(self, msg_ids, sends)

    async def check_native_permission(self):
        if isinstance(self.session.message, Message):
            info = self.session.message.member
            admins = ["2", "4"]
            for x in admins:
                if x in info.roles:
                    return True
        elif isinstance(self.session.message, DirectMessage):
            return True
        elif isinstance(self.session.message, GroupMessage):
            ...  # 群组好像无法获取成员权限信息...
        elif isinstance(self.session.message, C2CMessage):
            return True
        return False

    async def to_message_chain(self):
        lst = []
        lst.append(Plain(self.session.message.content))
        for x in self.session.message.attachments:
            d = await download(x.url)
            if filetype.is_image(d):
                lst.append(Image(d))
        return MessageChain(lst)

    def as_display(self, text_only=False):
        msg = self.session.message.content
        if self.target.target_from in [target_guild_prefix, target_direct_prefix]:
            msg = re.sub(r"<@(.*?)>", rf"{sender_tiny_prefix}|\1", msg)
        else:
            msg = re.sub(r"<@(.*?)>", rf"{sender_prefix}|\1", msg)
        return msg

    async def delete(self):
        if self.target.target_from in [target_guild_prefix, target_direct_prefix]:
            try:
                await self.session.message._api.recall_message(
                    channel_id=self.session.message.channel_id,
                    message_id=self.session.message.id,
                    hidetip=True,
                )
                return True
            except Exception:
                Logger.error(traceback.format_exc())
                return False
        else:
            return False

    sendMessage = send_message
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkNativePermission = check_native_permission

    class Typing:
        def __init__(self, msg: MessageSessionT):
            self.msg = msg

        async def __aenter__(self):
            if self.msg.target.target_from == target_guild_prefix:
                emoji_id = str(
                    Config("qq_typing_emoji", 181, (str, int), table_name="bot_qqbot")
                )
                emoji_type = 1 if int(emoji_id) < 9000 else 2
                from bots.qqbot.bot import client  # noqa

                await client.api.put_reaction(
                    channel_id=self.msg.target.target_id.split("|")[-1],
                    message_id=self.msg.target.message_id,
                    emoji_type=emoji_type,
                    emoji_id=emoji_id,
                )

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
        from bots.qqbot.bot import client  # noqa

        if self.target.target_from == target_guild_prefix:
            self.session.message = Message(
                api=client.api,
                event_id=None,
                data={"channel_id": self.target.target_id.split("|")[-1]},
            )
        elif self.target.target_from == target_direct_prefix:
            self.session.message = DirectMessage(
                api=client.api,
                event_id=None,
                data={"guild_id": self.target.target_id.split("|")[-1]},
            )
        elif self.target.target_from == target_group_prefix:
            self.session.message = GroupMessage(
                api=client.api,
                event_id=None,
                data={"group_openid": self.target.target_id.split("|")[-1]},
            )
        elif self.target.target_from == target_c2c_prefix:
            self.session.message = C2CMessage(
                api=client.api,
                event_id=None,
                data={"author": {"user_openid": self.target.target_id.split("|")[-1]}},
            )

        return await self.parent.send_direct_message(
            message_chain, disable_secret_check=disable_secret_check
        )


Bot.FetchedSession = FetchedSession


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        target_pattern = r"|".join(re.escape(item) for item in target_prefix_list)
        match_target = re.match(rf"^({target_pattern})\|(.*)", target_id)
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
        for x in target_list:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list=None, i18n=False, **kwargs):
        module_name = None if module_name == "*" else module_name
        if user_list:
            for x in user_list:
                try:
                    msgchain = message
                    if isinstance(message, str):
                        if i18n:
                            msgchain = MessageChain([I18NContext(message, **kwargs)])
                        else:
                            msgchain = MessageChain([Plain(message)])
                    msgchain = MessageChain(msgchain)
                    await x.send_direct_message(msgchain)
                    if enable_analytics and module_name:
                        await AnalyticsData.create(target_id=x.target.target_id,
                                                   sender_id=x.target.sender_id,
                                                   command="",
                                                   module_name=module_name,
                                                   module_type="schedule")
                except Exception:
                    Logger.error(traceback.format_exc())
        else:
            get_target_id = await TargetInfo.get_target_list_by_module(module_name, client_name)
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x.target_id)
                if fetch:
                    if x.muted:
                        continue
                    try:
                        msgchain = message
                        if isinstance(message, str):
                            if i18n:
                                msgchain = MessageChain([I18NContext(message, **kwargs)])
                            else:
                                msgchain = MessageChain([Plain(message)])
                        msgchain = MessageChain(msgchain)
                        await fetch.send_direct_message(msgchain)
                        if enable_analytics and module_name:
                            await AnalyticsData.create(target_id=fetch.target.target_id,
                                                       sender_id=fetch.target.sender_id,
                                                       command="",
                                                       module_name=module_name,
                                                       module_type="schedule")
                    except Exception:
                        Logger.error(traceback.format_exc())


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
