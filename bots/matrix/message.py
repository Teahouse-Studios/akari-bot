import asyncio
import mimetypes
import os
import re
import traceback
from typing import List, Union

from bots.matrix.client import bot, homeserver_host
from config import Config
from core.builtins import Bot, Plain, Image, Voice, MessageSession as MS, ErrorMessage
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import MsgInfo, Session, FetchTarget as FT, FetchedSession as FS, \
    FinishedSession as FinS
from core.utils.image import image_split
from database import BotDBUtil
import nio

enable_analytics = Config('enable_analytics')


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        try:
            for x in self.messageId:
                await bot.room_redact(str(self.result), x)
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MS):
    class Feature:
        image = True
        voice = True
        embed = False
        forward = False
        delete = True
        quote = True
        wait = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False,
                          allow_split_image=True) -> FinishedSession:
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(msgchain)
        send: list[nio.RoomSendResponse] = []
        for x in msgchain.asSendable(embed=False):
            replyTo = None
            if quote and len(send) == 0:
                replyTo = self.target.messageId

            if isinstance(x, Plain):
                content = {
                    'msgtype': 'm.notice',
                    'body': x.text
                }
                if replyTo:
                    # https://spec.matrix.org/v1.7/client-server-api/#fallbacks-for-rich-replies
                    # todo: standardize fallback for m.emote, m.image, m.video, m.audio, and m.file
                    content['body'] = f"> <{self.session.sender}> {self.session.message['content']['body']}\n\n{x.text}"
                    content['format'] = 'org.matrix.custom.html'
                    htmlText = x.text.replace('\n', '<br />')
                    content['formatted_body'] = f"<mx-reply><blockquote><a href=\"https://matrix.to/#/{self.session.target}/{replyTo}?via={homeserver_host}\">In reply to</a> <a href=\"https://matrix.to/#/{self.session.sender}\">{self.session.sender}</a><br/>{self.session.message['content']['body']}</blockquote></mx-reply>{htmlText}"
                Logger.info(f'[Bot] -> [{self.target.targetId}]: {x.text}')
            elif isinstance(x, Image):
                split = [x]
                if allow_split_image:
                    split = await image_split(x)
                for xs in split:
                    path = await xs.get()
                    with open(path, 'rb') as image:
                        filename = os.path.basename(path)
                        filesize = os.path.getsize(path)
                        (contentType, contentEncoding) = mimetypes.guess_type(path)
                        if contentType is None or contentEncoding is None:
                            contentType = 'image'
                            contentEncoding = 'png'
                        mimetype = f"{contentType}/{contentEncoding}"

                        (upload, upload_encryption) = await bot.upload(
                            image,
                            content_type=mimetype,
                            filename=filename,
                            encrypt=False,
                            filesize=filesize)
                        Logger.info(
                            f"Uploaded image {filename} to media repo, uri: {upload.content_uri}, mime: {mimetype}")
                        # todo: provide more image info
                        content = {
                            'msgtype': 'm.image',
                            'url': upload.content_uri,
                            'body': filename,
                            'info': {
                                'size': filesize,
                                'mimetype': mimetype,
                            }
                        }
                        Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {str(xs.__dict__)}')
            elif isinstance(x, Voice):
                path = x.path
                filename = os.path.basename(path)
                filesize = os.path.getsize(path)
                (contentType, contentEncoding) = mimetypes.guess_type(path)
                if contentType is None or contentEncoding is None:
                    contentType = 'audio'
                    contentEncoding = 'ogg'
                mimetype = f"{contentType}/{contentEncoding}"

                with open(path, 'rb') as audio:
                    (upload, upload_encryption) = await bot.upload(
                        audio,
                        content_type=mimetype,
                        filename=filename,
                        encrypt=False,
                        filesize=filesize)
                Logger.info(
                    f"Uploaded audio {filename} to media repo, uri: {upload.content_uri}, mime: {mimetype}")
                # todo: provide audio duration info
                content = {
                    'msgtype': 'm.audio',
                    'url': upload.content_uri,
                    'body': filename,
                    'info': {
                        'size': filesize,
                        'mimetype': mimetype,
                    }
                }
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Voice: {str(x.__dict__)}')

            if replyTo:
                # rich reply
                content['m.relates_to'] = {
                    'm.in_reply_to': {
                        'event_id': replyTo
                    }
                }
            # todo https://github.com/poljar/matrix-nio/pull/417
            resp: nio.RoomSendResponse = await bot.room_send(self.session.target, 'm.room.message', content)
            if resp is nio.RoomSendError:
                Logger.error(f"Error in sending message: {resp}")
            else:
                send.append(resp)

        return FinishedSession(self, [resp.event_id for resp in send], self.session.target)

    async def checkPermission(self):
        if self.target.senderId in self.custom_admins or self.target.senderInfo.query.isSuperUser:
            return True
        return await self.checkNativePermission()

    async def checkNativePermission(self):
        if self.session.target.startswith('@') or self.session.sender.startswith('!'):
            return True
        # https://spec.matrix.org/v1.7/client-server-api/#permissions
        powerLevels = await bot.room_get_state_event(self.session.target, 'm.room.power_levels')
        level = powerLevels.content['users'][self.session.sender]
        if level is not None and level >= 50:
            return True
        return False

    def asDisplay(self, text_only=False):
        if not text_only or self.session.message['content']['msgtype'] == 'm.text':
            return str(self.session.message['content']['body'])
        if not text_only and 'format' in self.session.message['content']:
            return str(self.session.message['content']['formatted_body'])
        return ''

    async def toMessageChain(self):
        content = self.session.message['content']
        msgtype = content['msgtype']
        if msgtype == 'm.emote':
            msgtype = 'm.text'
        match msgtype:
            case 'm.text':
                text = str(content['body'])
                if self.target.replyId is not None:
                    # redact the fallback line for rich reply
                    # https://spec.matrix.org/v1.7/client-server-api/#fallbacks-for-rich-replies
                    while text.startswith('> '):
                        text = ''.join(text.splitlines(keepends=True)[1:])
                return MessageChain(Plain(text.strip()))
            case 'm.image':
                url = str(content['url'])
                return MessageChain(Image(await bot.mxc_to_http(url)))
            case 'm.audio':
                # url = str(content['url'])
                # return MessageChain(Voice(await bot.mxc_to_http(url)))
                # todo: receive audio messages
                pass
        Logger.error(f"Got unknown msgtype: {msgtype}")
        return MessageChain([])

    async def delete(self):
        try:
            await bot.room_redact(self.session.target, self.session.message['event_id'])
        except Exception:
            Logger.error(traceback.format_exc())

    # https://spec.matrix.org/v1.7/client-server-api/#typing-notifications
    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            await bot.room_typing(self.msg.session.target, True)
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await bot.room_typing(self.msg.session.target, False)
            pass


class FetchedSession(FS):
    def __init__(self, targetFrom, targetId):
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{targetFrom}|{targetId}',
                              targetFrom=targetFrom,
                              senderFrom=targetFrom,
                              senderName='',
                              clientName='Matrix', messageId=None, replyId=None)
        self.session = Session(message=False, target=targetId, sender=targetId)
        self.parent = MessageSession(self.target, self.session)

    async def _resolve_matrix_room_(self):
        targetId: str = self.session.target
        if targetId.startswith('@'):
            # find private messaging room
            for room in bot.rooms:
                room = bot.rooms[room]
                if room.join_rule == 'invite' and room.member_count == 2:
                    resp = await bot.room_get_state_event(room.room_id, 'm.room.member', targetId)
                    if resp is nio.ErrorResponse:
                        pass
                    elif resp.content['membership'] == 'join':
                        self.session.target = room.room_id
                        return
            Logger.info(f"Could not find any exist private room for {targetId}, trying to create one")
            resp = await bot.room_create(visibility=nio.RoomVisibility.private,
                                         is_direct=True,
                                         preset=nio.RoomPreset.trusted_private_chat,
                                         invite=[targetId],)
            if resp is nio.ErrorResponse:
                pass
            room = resp.room_id
            Logger.info(f"Created private messaging room for {targetId}: {room}")
            self.session.target = room


class FetchTarget(FT):
    name = 'Matrix'

    @staticmethod
    async def fetch_target(targetId) -> Union[FetchedSession, bool]:
        matchChannel = re.match(r'^(Matrix)\|(.*)', targetId)
        if matchChannel:
            session = FetchedSession(matchChannel.group(1), matchChannel.group(2))
            await session._resolve_matrix_room_()
            return session
        else:
            return False

    @staticmethod
    async def fetch_target_list(targetList: list) -> List[FetchedSession]:
        lst = []
        for x in targetList:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[FetchedSession] = None, i18n=False, **kwargs):
        if user_list is not None:
            for x in user_list:
                try:
                    if i18n:
                        if isinstance(message, dict):
                            if (gm := message.get(x.parent.locale.locale)) is not None:
                                await x.sendDirectMessage(gm)
                            else:
                                await x.sendDirectMessage(message.get('fallback'))
                        else:
                            await x.sendDirectMessage(x.parent.locale.t(message, **kwargs))

                    else:
                        await x.sendDirectMessage(message)
                    if enable_analytics:
                        BotDBUtil.Analytics(x).add('', module_name, 'schedule')
                except Exception:
                    Logger.error(traceback.format_exc())
        else:
            get_target_id = BotDBUtil.TargetInfo.get_enabled_this(module_name, "Matrix")
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x.targetId)
                if fetch:
                    try:
                        if i18n:
                            if isinstance(message, dict):
                                if (gm := message.get(fetch.parent.locale.locale)) is not None:
                                    await fetch.sendDirectMessage(gm)
                                else:
                                    await fetch.sendDirectMessage(message.get('fallback'))
                            else:
                                await fetch.sendDirectMessage(fetch.parent.locale.t(message, **kwargs))

                        else:
                            await fetch.sendDirectMessage(message)
                        if enable_analytics:
                            BotDBUtil.Analytics(fetch).add('', module_name, 'schedule')
                    except Exception:
                        Logger.error(traceback.format_exc())


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
