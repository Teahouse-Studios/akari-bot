import re
import traceback
from typing import List, Union

from aiogram.types import FSInputFile

from bots.aiogram.client import bot, token
from bots.aiogram.info import *
from core.builtins import (
    Bot,
    Plain,
    Image,
    Voice,
    MessageSession as MessageSessionT,
    I18NContext,
    MessageTaskManager,
    FetchTarget as FetchTargetT,
    FinishedSession as FinishedSessionT,
)
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement
from core.config import Config
from core.database.models import AnalyticsData, TargetInfo
from core.logger import Logger
from core.utils.http import download
from core.utils.image import image_split

enable_analytics = Config("enable_analytics", False)


class FinishedSession(FinishedSessionT):
    async def delete(self):
        try:
            for x in self.result:
                await x.delete()
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = True
        mention = True
        embed = False
        forward = False
        delete = True
        markdown = False
        quote = True
        rss = True
        typing = False
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
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(I18NContext("error.message.chain.unsafe"))
        self.sent.append(message_chain)
        count = 0
        send = []
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, PlainElement):
                send_ = await bot.send_message(
                    self.session.target,
                    x.text,
                    reply_to_message_id=(
                        self.session.message.message_id
                        if quote and count == 0 and self.session.message
                        else None
                    ),
                )
                Logger.info(f"[Bot] -> [{self.target.target_id}]: {x.text}")
                send.append(send_)
                count += 1
            elif isinstance(x, ImageElement):
                if enable_split_image:
                    split = await image_split(x)
                    for xs in split:
                        send_ = await bot.send_photo(
                            self.session.target,
                            FSInputFile(await xs.get()),
                            reply_to_message_id=(
                                self.session.message.message_id
                                if quote and count == 0 and self.session.message
                                else None
                            ),
                        )
                        Logger.info(
                            f"[Bot] -> [{self.target.target_id}]: Image: {str(xs.__dict__)}"
                        )
                        send.append(send_)
                        count += 1
                else:
                    send_ = await bot.send_photo(
                        self.session.target,
                        FSInputFile(await x.get()),
                        reply_to_message_id=(
                            self.session.message.message_id
                            if quote and count == 0 and self.session.message
                            else None
                        ),
                    )
                    Logger.info(
                        f"[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}"
                    )
                    send.append(send_)
                    count += 1
            elif isinstance(x, VoiceElement):
                send_ = await bot.send_audio(
                    self.session.target,
                    FSInputFile(x.path),
                    reply_to_message_id=(
                        self.session.message.message_id
                        if quote and count == 0 and self.session.message
                        else None
                    ),
                )
                Logger.info(
                    f"[Bot] -> [{self.target.target_id}]: Voice: {str(x.__dict__)}"
                )
                send.append(send_)
                count += 1
            elif isinstance(x, MentionElement):
                if x.client == client_name and self.target.target_from in [
                        f"{client_name}|Group", f"{client_name}|Supergroup"]:
                    send_ = await bot.send_message(
                        self.session.target,
                        f"<a href=\"tg://user?id={x.id}\">@{x.id}</a>",
                        reply_to_message_id=(
                            self.session.message.message_id
                            if quote and count == 0 and self.session.message
                            else None
                        ), parse_mode="HTML"
                    )
                    Logger.info(f"[Bot] -> [{self.target.target_id}]: Mention: {sender_prefix}|{x.id}")
                    send.append(send_)
                    count += 1

        msg_ids = []
        for x in send:
            msg_ids.append(x.message_id)
            if callback:
                MessageTaskManager.add_callback(x.message_id, callback)
        return FinishedSession(self, msg_ids, send)

    async def check_native_permission(self):
        if not self.session.message:
            chat = await bot.get_chat(self.session.target)
        else:
            chat = self.session.message.chat
        if chat.type == "private":
            return True
        admins = [
            member.user.id for member in await bot.get_chat_administrators(chat.id)
        ]
        if self.session.sender in admins:
            return True
        return False

    def as_display(self, text_only=False):
        if self.session.message.text:
            return self.session.message.text
        return ""

    async def to_message_chain(self):
        lst = []
        if self.session.message.audio:
            file = await bot.get_file(self.session.message.audio.file_id)
            d = await download(
                f"https://api.telegram.org/file/bot{token}/{file.file_path}"
            )
            lst.append(Voice(d))
        if self.session.message.photo:
            file = await bot.get_file(self.session.message.photo[-1]["file_id"])
            lst.append(
                Image(f"https://api.telegram.org/file/bot{token}/{file.file_path}")
            )
        if self.session.message.voice:
            file = await bot.get_file(self.session.message.voice.file_id)
            d = await download(
                f"https://api.telegram.org/file/bot{token}/{file.file_path}"
            )
            lst.append(Voice(d))
        if self.session.message.caption:
            lst.append(Plain(self.session.message.caption))
        if self.session.message.text:
            lst.append(Plain(self.session.message.text))
        return MessageChain(lst)

    async def delete(self):
        try:
            for x in self.session.message:
                await x.delete()
            return True
        except Exception:
            Logger.error(traceback.format_exc())
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
    async def fetch_target_list(target_list: list) -> List[Bot.FetchedSession]:
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
            get_target_id = await TargetInfo.get_target_list_by_module(
                module_name, client_name
            )
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
