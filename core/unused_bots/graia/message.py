import asyncio
import re
import traceback
from typing import List
from core.logger import Logger

from graia.application import MessageChain, GroupMessage, FriendMessage
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.elements.internal import Plain, Image, Source, Voice
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter

from config import Config
from core.elements import Plain as BPlain, Image as BImage, Voice as BVoice, MessageSession as MS, MsgInfo, Session, \
    FetchTarget as FT, ErrorMessage
from core.elements.others import confirm_command
from core.unused_bots.graia.broadcast import app, bcc
from core.utils import slk_converter
from database import BotDBUtil
from database.logging_message import LoggerMSG


async def msgchain_gen(message) -> MessageChain:
    if isinstance(message, str):
        if message == '':
            message = ErrorMessage('机器人尝试发送空文本消息，请联系机器人开发者解决问题。')
        msgchain = MessageChain.create([Plain(message)])
    elif isinstance(message, (list, tuple)):
        msgchain_list = []
        for x in message:
            if isinstance(x, BPlain):
                msgchain_list.append(Plain(x.text))
            if isinstance(x, BImage):
                msgchain_list.append(Image.fromLocalFile(await x.get()))
            if isinstance(x, BVoice):
                msgchain_list.append(Voice().fromLocalFile(filepath=await slk_converter(x.path)))
        if not msgchain_list:
            msgchain_list.append(Plain(ErrorMessage('机器人尝试发送空文本消息，请联系机器人开发者解决问题。')))
        msgchain = MessageChain.create(msgchain_list)
    elif isinstance(message, MessageChain):
        msgchain = message
    else:
        msgchain = MessageChain.create([Plain(ErrorMessage('机器人尝试发送非法消息链，请联系机器人开发者解决问题。'))])
    return msgchain


class MessageSession(MS):
    class Feature:
        image = True
        voice = True

    async def sendMessage(self, msgchain, quote=True):
        msgchain = await msgchain_gen(msgchain)
        if Config('qq_msg_logging_to_db') and self.session.message:
            LoggerMSG(userid=self.target.senderId, command=self.trigger_msg, msg=msgchain.asDisplay())
        if isinstance(self.session.target, Group) or self.target.targetFrom == 'QQ|Group':
            send = await app.sendGroupMessage(self.session.target, msgchain, quote=self.session.message[Source][0].id
            if quote and self.session.message else None)
            return MessageSession(
                target=MsgInfo(targetId=0, senderId=0, targetFrom='QQ|Bot', senderFrom="QQ|Bot", senderName=''),
                session=Session(message=send, target=0, sender=0))
        if isinstance(self.session.target, Friend) or self.target.targetFrom == 'QQ':
            send = await app.sendFriendMessage(self.session.target, msgchain)
            return MessageSession(
                target=MsgInfo(targetId=0, senderId=0, targetFrom='QQ|Bot', senderFrom="QQ|Bot", senderName=''),
                session=Session(message=send, target=0, sender=0))

    async def waitConfirm(self, msgchain=None, quote=True):
        if msgchain is not None:
            msgchain = await msgchain_gen(msgchain)
            msgchain = msgchain.plusWith(MessageChain.create([Plain('（发送“是”或符合确认条件的词语来确认）')]))
            send = await self.sendMessage(msgchain, quote=quote)
        inc = InterruptControl(bcc)
        if isinstance(self.session.target, Group):
            @Waiter.create_using_function([GroupMessage])
            def waiter(waiter_group: Group,
                       waiter_member: Member, waiter_message: MessageChain):
                if all([
                    waiter_group.id == self.session.target.id,
                    waiter_member.id == self.session.sender.id,
                ]):
                    if waiter_message.asDisplay() in confirm_command:
                        return True
                    else:
                        return False
        elif isinstance(self.session.target, Friend):
            @Waiter.create_using_function([FriendMessage])
            def waiter(waiter_friend: Friend, waiter_message: MessageChain):
                if all([
                    waiter_friend.id == self.session.sender.id,
                ]):
                    if waiter_message.asDisplay() in confirm_command:
                        return True
                    else:
                        return False

        wait = await inc.wait(waiter)
        if msgchain is not None:
            await send.delete()
        return wait

    def asDisplay(self):
        display = self.session.message.asDisplay()
        return display

    async def delete(self):
        """
        用于撤回消息。
        :param send_msg: 需要撤回的已发送/接收的消息链
        :return: 无返回
        """
        try:
            await app.revokeMessage(self.session.message)
        except Exception:
            Logger.error(traceback.format_exc())

    async def checkPermission(self):
        """
        检查对象是否拥有某项权限
        :param display_msg: 从函数传入的dict
        :return: 若对象为群主、管理员或机器人超管则为True
        """
        if isinstance(self.session.target, Group):
            if str(self.session.sender.permission) in ['MemberPerm.Administrator', 'MemberPerm.Owner'] \
                or self.target.senderInfo.query.isSuperUser \
                or self.target.senderInfo.check_TargetAdmin(self.target.targetId):
                return True
        if isinstance(self.session.target, Friend):
            return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            if isinstance(self.msg.session.target, Group):
                try:
                    await app.nudge(self.msg.session.sender)
                except Exception:
                    Logger.error(traceback.format_exc())

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FT):
    @staticmethod
    async def fetch_target(targetId) -> MessageSession:
        matchTarget = re.match(r'^((?:QQ\|Group|QQ))\|(.*)', targetId)
        if matchTarget:
            return MessageSession(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                          targetFrom=matchTarget.group(1), senderFrom=matchTarget.group(1)),
                                  Session(message=False, target=int(matchTarget.group(2)),
                                          sender=int(matchTarget.group(2))))
        else:
            return False

    @staticmethod
    async def post_message(module_name, message, user_list: List[MessageSession] = None):
        send_list = []
        if user_list is not None:
            for x in user_list:
                try:
                    send = await x.sendMessage(message, quote=False)
                    send_list.append(send)
                except Exception:
                    Logger.error(traceback.format_exc())
        else:
            get_target_id = BotDBUtil.Module.get_enabled_this(module_name)
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x)
                if fetch:
                    try:
                        send = await fetch.sendMessage(message, quote=False)
                        send_list.append(send)
                        await asyncio.sleep(0.5)
                    except Exception:
                        Logger.error(traceback.format_exc())
        return send_list
