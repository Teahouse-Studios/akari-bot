import mimetypes
import os
import re
import traceback
from typing import List, Union

import nio

from bots.matrix.client import bot, homeserver_host
from bots.matrix.info import *
from core.builtins import Bot, Plain, Image, Voice, MessageSession as MessageSessionT, I18NContext, MessageTaskManager, \
    FetchTarget as FetchedTargetT, FinishedSession as FinishedSessionT
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement
from core.config import Config
from core.database import BotDBUtil
from core.logger import Logger
from core.utils.image import image_split

enable_analytics = Config("enable_analytics", False)


class FinishedSession(FinishedSessionT):
    async def delete(self):
        try:
            for x in self.message_id:
                await bot.room_redact(str(self.result), x)
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = True
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
            return await self.send_message((I18NContext("error.message.chain.unsafe", locale=self.locale.locale)))
        self.sent.append(message_chain)
        sentMessages: list[nio.RoomSendResponse] = []
        for x in message_chain.as_sendable(self, embed=False):

            async def sendMsg(content):
                reply_to = None
                reply_to_user = None
                if quote and len(sentMessages) == 0:
                    reply_to = self.target.message_id
                    reply_to_user = self.session.sender

                if reply_to:
                    # rich reply
                    content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
                    # mention target user
                    content["m.mentions"] = {"user_ids": [reply_to_user]}
                    if content["msgtype"] == "m.notice" and self.session.message:
                        # https://spec.matrix.org/v1.9/client-server-api/#fallbacks-for-rich-replies
                        # todo: standardize fallback for m.image, m.video, m.audio, and m.file
                        reply_to_type = self.session.message["content"]["msgtype"]
                        content["body"] = (f">{' *' if reply_to_type == 'm.emote' else ''} <{self.session.sender}> {
                            self.session.message['content']['body']}\n\n{x.text}")
                        content["format"] = "org.matrix.custom.html"
                        html_text = x.text
                        html_text = html_text.replace("<", "&lt;").replace(">", "&gt;")
                        html_text = html_text.replace("\n", "<br />")
                        content["formatted_body"] = (
                            f"<mx-reply><blockquote><a href=\"https://matrix.to/#/{
                                self.session.target}/{reply_to}?via={homeserver_host}\">In reply to</a>{
                                ' *' if reply_to_type == 'm.emote' else ''} <a href=\"https://matrix.to/#/{
                                self.session.sender}\">{
                                self.session.sender}</a><br/>{
                                self.session.message['content']['body']}</blockquote></mx-reply>{html_text}")

                if (
                    self.session.message
                    and "m.relates_to" in self.session.message["content"]
                ):
                    relates_to = self.session.message["content"]["m.relates_to"]
                    if (
                        "rel_type" in relates_to
                        and relates_to["rel_type"] == "m.thread"
                    ):
                        # replying in thread
                        thread_root = relates_to["event_id"]
                        if reply_to:
                            # reply to msg replying in thread
                            content["m.relates_to"] = {
                                "rel_type": "m.thread",
                                "event_id": thread_root,
                                "is_falling_back": False,
                                "m.in_reply_to": {"event_id": reply_to},
                            }
                        else:
                            # reply in thread
                            content["m.relates_to"] = {
                                "rel_type": "m.thread",
                                "event_id": thread_root,
                                "is_falling_back": True,
                                "m.in_reply_to": {"event_id": self.target.message_id},
                            }

                resp = await bot.room_send(
                    self.session.target,
                    "m.room.message",
                    content,
                    ignore_unverified_devices=True,
                )
                if "status_code" in resp.__dict__:
                    Logger.error(f"Error while sending message: {str(resp)}")
                else:
                    sentMessages.append(resp)
                reply_to = None
                reply_to_user = None

            if isinstance(x, PlainElement):
                content = {"msgtype": "m.notice", "body": x.text}
                Logger.info(f"[Bot] -> [{self.target.target_id}]: {x.text}")
                await sendMsg(content)
            elif isinstance(x, ImageElement):
                split = [x]
                if enable_split_image:
                    Logger.info(f"Split image: {str(x.__dict__)}")
                    split = await image_split(x)
                for xs in split:
                    path = await xs.get()
                    with open(path, "rb") as image:
                        filename = os.path.basename(path)
                        filesize = os.path.getsize(path)
                        (content_type, content_encoding) = mimetypes.guess_type(path)
                        if not content_type or not content_encoding:
                            content_type = "image"
                            content_encoding = "png"
                        mimetype = f"{content_type}/{content_encoding}"

                        encrypted = self.session.target in bot.encrypted_rooms
                        (upload, upload_encryption) = await bot.upload(
                            image,
                            content_type=mimetype,
                            filename=filename,
                            encrypt=encrypted,
                            filesize=filesize,
                        )
                        Logger.info(
                            f"Uploaded image {filename} to media repo, uri: {
                                upload.content_uri}, mime: {mimetype}, encrypted: {encrypted}")
                        # todo: provide more image info
                        if not encrypted:
                            content = {
                                "msgtype": "m.image",
                                "url": upload.content_uri,
                                "body": filename,
                                "info": {
                                    "size": filesize,
                                    "mimetype": mimetype,
                                },
                            }
                        else:
                            upload_encryption["url"] = upload.content_uri
                            content = {
                                "msgtype": "m.image",
                                "body": filename,
                                "file": upload_encryption,
                                "info": {
                                    "size": filesize,
                                    "mimetype": mimetype,
                                },
                            }
                        Logger.info(
                            f"[Bot] -> [{self.target.target_id}]: Image: {str(xs.__dict__)}"
                        )
                        await sendMsg(content)
            elif isinstance(x, VoiceElement):
                path = x.path
                filename = os.path.basename(path)
                filesize = os.path.getsize(path)
                (content_type, content_encoding) = mimetypes.guess_type(path)
                if not content_type or not content_encoding:
                    content_type = "audio"
                    content_encoding = "ogg"
                mimetype = f"{content_type}/{content_encoding}"

                encrypted = self.session.target in bot.encrypted_rooms
                with open(path, "rb") as audio:
                    (upload, upload_encryption) = await bot.upload(
                        audio,
                        content_type=mimetype,
                        filename=filename,
                        encrypt=encrypted,
                        filesize=filesize,
                    )
                Logger.info(f"Uploaded audio {filename} to media repo, uri: {
                    upload.content_uri}, mime: {mimetype}, encrypted: {encrypted}")
                # todo: provide audio duration info
                if not encrypted:
                    content = {
                        "msgtype": "m.audio",
                        "url": upload.content_uri,
                        "body": filename,
                        "info": {
                            "size": filesize,
                            "mimetype": mimetype,
                        },
                    }
                else:
                    upload_encryption["url"] = upload.content_uri
                    content = {
                        "msgtype": "m.audio",
                        "body": filename,
                        "file": upload_encryption,
                        "info": {
                            "size": filesize,
                            "mimetype": mimetype,
                        },
                    }

                Logger.info(
                    f"[Bot] -> [{self.target.target_id}]: Voice: {str(x.__dict__)}"
                )
                await sendMsg(content)
        if callback:
            for x in sentMessages:
                MessageTaskManager.add_callback(x.event_id, callback)
        return FinishedSession(
            self, [resp.event_id for resp in sentMessages], self.session.target
        )

    async def check_native_permission(self):
        if self.session.target.startswith("@") or self.session.sender.startswith("!"):
            return True
        # https://spec.matrix.org/v1.9/client-server-api/#permissions
        power_levels = (
            await bot.room_get_state_event(self.session.target, "m.room.power_levels")
        ).content
        level = (
            power_levels["users"][self.session.sender]
            if self.session.sender in power_levels["users"]
            else power_levels["users_default"]
        )
        if level and int(level) >= 50:
            return True
        return False

    def as_display(self, text_only=False):
        if not self.session.message:
            return ""
        if not text_only or self.session.message["content"]["msgtype"] == "m.text":
            return str(self.session.message["content"]["body"])
        if not text_only and "format" in self.session.message["content"]:
            return str(self.session.message["content"]["formatted_body"])
        return ""

    async def to_message_chain(self):
        if not self.session.message:
            return MessageChain([])
        content = self.session.message["content"]
        msgtype = content["msgtype"]
        if msgtype == "m.emote":
            msgtype = "m.text"
        if msgtype == "m.text":  # compatible with py38
            text = str(content["body"])
            if self.target.reply_id:
                # redact the fallback line for rich reply
                # https://spec.matrix.org/v1.9/client-server-api/#fallbacks-for-rich-replies
                while text.startswith("> "):
                    text = "".join(text.splitlines(keepends=True)[1:])
            return MessageChain(Plain(text.strip()))
        if msgtype == "m.image":
            url = None
            if "url" in content:
                url = str(content["url"])
            elif "file" in content:
                # todo: decrypt image
                # url = str(content['file']['url'])
                return MessageChain([])
            else:
                Logger.error(f"Got invalid m.image message from {self.session.target}")
            return MessageChain(Image(await bot.mxc_to_http(url)))
        if msgtype == "m.audio":
            url = str(content["url"])
            return MessageChain(Voice(await bot.mxc_to_http(url)))
        Logger.error(f"Got unknown msgtype: {msgtype}")
        return MessageChain([])

    async def delete(self):
        try:
            await bot.room_redact(self.session.target, self.session.message["event_id"])
            return True
        except Exception:
            Logger.error(traceback.format_exc())
            return False

    sendMessage = send_message
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkNativePermission = check_native_permission

    # https://spec.matrix.org/v1.9/client-server-api/#typing-notifications
    class Typing:
        def __init__(self, msg: MessageSessionT):
            self.msg = msg

        async def __aenter__(self):
            await bot.room_typing(self.msg.session.target, True)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await bot.room_typing(self.msg.session.target, False)


class FetchedSession(Bot.FetchedSession):

    async def _resolve_matrix_room_(self):
        target_id: str = self.session.target
        if target_id.startswith("@"):
            # find private messaging room
            for room in bot.rooms:
                room = bot.rooms[room]
                if room.join_rule == "invite" and (
                    (room.member_count == 2 and target_id in room.users)
                    or (room.member_count == 1 and target_id in room.invited_users)
                ):
                    resp = await bot.room_get_state_event(
                        room.room_id, "m.room.member", target_id
                    )
                    if resp is nio.ErrorResponse:
                        pass
                    elif resp.content["membership"] in ["join", "leave", "invite"]:
                        self.session.target = room.room_id
                        return
            Logger.info(
                f"Could not find any exist private room for {target_id}, trying to create one."
            )
            try:
                resp = await bot.room_create(
                    visibility=nio.RoomVisibility.private,
                    is_direct=True,
                    preset=nio.RoomPreset.trusted_private_chat,
                    invite=[target_id],
                )
                room = resp.room_id
                Logger.info(f"Created private messaging room for {target_id}: {room}")
                self.session.target = room
            except Exception as e:
                Logger.error(f"Failed to create room for {target_id}: {e}")
                return


Bot.FetchedSession = FetchedSession


class FetchTarget(FetchedTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        target_pattern = r'|'.join(re.escape(item) for item in target_prefix_list)
        match_target = re.match(fr"^({target_pattern})\|(.*)", target_id)
        if match_target:
            target_from = sender_from = match_target.group(1)
            target_id = match_target.group(2)
            if sender_id:
                sender_pattern = r'|'.join(re.escape(item) for item in sender_prefix_list)
                match_sender = re.match(fr"^({sender_pattern})\|(.*)", sender_id)
                if match_sender:
                    sender_from = match_sender.group(1)
                    sender_id = match_sender.group(2)
            else:
                sender_id = target_id
            session = Bot.FetchedSession(target_from, target_id, sender_from, sender_id)
            await session._resolve_matrix_room_()
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
        module_name = None if module_name == '*' else module_name
        if user_list:
            for x in user_list:
                try:
                    msgchain = message
                    if isinstance(message, str):
                        if i18n:
                            msgchain = MessageChain([Plain(x.parent.locale.t(message, **kwargs))])
                        else:
                            msgchain = MessageChain([Plain(message)])
                    msgchain = MessageChain(msgchain)
                    await x.send_direct_message(msgchain)
                    if enable_analytics and module_name:
                        BotDBUtil.Analytics(x).add("", module_name, "schedule")
                except Exception:
                    Logger.error(traceback.format_exc())
        else:
            get_target_id = BotDBUtil.TargetInfo.get_target_list(module_name, client_name)
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x.targetId)
                if fetch:
                    if BotDBUtil.TargetInfo(fetch.target.target_id).is_muted:
                        continue
                    try:
                        msgchain = message
                        if isinstance(message, str):
                            if i18n:
                                msgchain = MessageChain([Plain(fetch.parent.locale.t(message, **kwargs))])
                            else:
                                msgchain = MessageChain([Plain(message)])
                        msgchain = MessageChain(msgchain)
                        await fetch.send_direct_message(msgchain)
                        if enable_analytics and module_name:
                            BotDBUtil.Analytics(fetch).add("", module_name, "schedule")
                    except Exception:
                        Logger.error(traceback.format_exc())


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
