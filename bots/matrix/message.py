import os
import re
import traceback
from typing import List, Union

from bots.matrix.client import bot
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
                x = str(x).split('|', 2)
                room_id = x[0]
                event_id = x[1]
                await bot.room_redact(room_id, event_id)
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MS):
    class Feature:
        image = True
        voice = False
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
                Logger.info(f'[Bot] -> [{self.target.targetId}]: {x.text}')
            elif isinstance(x, Image):
                split = [x]
                if allow_split_image:
                    split = await image_split(x)
                for xs in split:
                    path = await xs.get()
                    with open(path, 'rb') as image:
                        bot.upload(
                            image,
                            content_type="image/png",
                            filename=os.path.basename(path),
                            encrypt=False,
                            filesize=os.path.getsize(path))
                        Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {str(xs.__dict__)}')
            elif isinstance(x, Voice):
                # todo voice support
                pass

            if replyTo:
                # rich reply
                content['m.relates_to'] = {
                    'm.in_reply_to': {
                        'event_id': replyTo
                    }
                }
            # todo https://github.com/poljar/matrix-nio/pull/417
            resp: nio.RoomSendResponse = await bot.room_send(self.session.target, 'm.room.message', content)
            send.append(resp)

        msgIds = []
        for resp in send:
            msgIds.append(f'{resp.room_id}|{resp.event_id}')
        return FinishedSession(self, msgIds, send)

    async def checkPermission(self):
        if self.target.senderId in self.custom_admins or self.target.senderInfo.query.isSuperUser:
            return True
        return await self.checkNativePermission()

    async def checkNativePermission(self):
        if self.session.target.startswith('@'):
            return True
        # https://spec.matrix.org/v1.7/client-server-api/#permissions
        powerLevels = await bot.room_get_state_event(self.session.target, 'm.room.power_levels')
        level = powerLevels['users'][self.session.sender]
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
        match msgtype:
            case 'm.text':
                text = str(content['body'])
                if self.target.replyId is not None:
                    # redact the fallback line for rich reply
                    # https://spec.matrix.org/v1.7/client-server-api/#fallbacks-for-rich-replies
                    text = ''.join(text.splitlines(keepends=True)[2:])
                    pass
                return MessageChain(Plain(text.strip()))
            case 'm.image':
                url = str(content['url'])
                return MessageChain(Image(await bot.mxc_to_http(url)))
        Logger.error(f"Got unknown msgtype: {msgtype}")
        return MessageChain([])

    async def delete(self):
        try:
            await bot.room_redact(self.session.target, self.session.message['event_id'])
        except Exception:
            Logger.error(traceback.format_exc())

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
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


class FetchTarget(FT):
    name = 'Matrix'

    @staticmethod
    async def fetch_target(targetId) -> Union[FetchedSession, bool]:
        matchChannel = re.match(r'^(Matrix)\|(.*)', targetId)
        if matchChannel:
            return FetchedSession(matchChannel.group(1), matchChannel.group(2))
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
