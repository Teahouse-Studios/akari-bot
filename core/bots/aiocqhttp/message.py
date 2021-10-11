import asyncio
import re
import traceback
from typing import List
from pathlib import Path

from aiocqhttp import MessageSegment
from core.bots.aiocqhttp.client import bot
from core.bots.aiocqhttp.tasks import MessageTaskManager, FinishedTasks
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session, Voice, FetchTarget as FT
from core.elements.others import confirm_command
from core.logger import Logger
from database import BotDBUtil
import html


def convert2lst(s) -> list:
    if isinstance(s, str):
        return [Plain(s)]
    elif isinstance(s, list):
        return s
    elif isinstance(s, tuple):
        return list(s)


class MessageSession(MS):
    class Feature:
        image = True
        voice = True
        forward = True

    async def sendMessage(self, msgchain, quote=True):
        msg = MessageSegment.text('')
        if quote:
            msg = MessageSegment.reply(self.session.message.message_id)
        if isinstance(msgchain, str):
            msg = msg + (MessageSegment.text(msgchain) if msgchain != '' else '发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。'
                                                                              '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title=')
        elif isinstance(msgchain, (list, tuple)):
            for x in msgchain:
                if isinstance(x, Plain):
                    msg = msg + MessageSegment.text(x.text)
                elif isinstance(x, Image):
                    msg = msg + MessageSegment.image(Path(await x.get()).as_uri())
                elif isinstance(x, Voice):
                    msg = msg + MessageSegment.record(Path(x.path).as_uri())
        else:
            msg = msg + MessageSegment.text('发生错误：机器人尝试发送非法消息链，请联系机器人开发者解决问题。'
                                            '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title=')
        Logger.info(f'[Bot] -> [{self.target.targetId}]: {msg}')
        if self.target.targetFrom == 'QQ|Group':
            send = await bot.send_group_msg(group_id=self.session.target, message=msg)
        else:
            send = await bot.send_private_msg(user_id=self.session.target, message=msg)

        return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='QQ|Bot',
                                             senderFrom='QQ|Bot'),
                              session=Session(message=send,
                                              target=self.session.target,
                                              sender=self.session.sender))

    async def waitConfirm(self, msgchain=None, quote=True):
        send = None
        if msgchain is not None:
            msgchain = convert2lst(msgchain)
            msgchain.append(Plain('（发送“是”或符合确认条件的词语来确认）'))
            send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self.session.sender, flag)
        await flag.wait()
        if send is not None:
            await send.delete()
        if FinishedTasks.get()[self.session.sender] in confirm_command:
            return True
        return False

    async def checkPermission(self):
        if self.target.targetFrom == 'QQ' or self.target.senderInfo.check_TargetAdmin(
                self.target.targetId):
            return True
        get_member_info = await bot.call_action('get_group_member_info', group_id=self.session.target, user_id=self.session.sender)
        if get_member_info['role'] in ['owner', 'admin']:
            return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    def asDisplay(self):

        return html.unescape(self.session.message.message)

    async def fake_forward_msg(self, nodelist):
        if self.target.targetFrom == 'QQ|Group':
            await bot.call_action('send_group_forward_msg', group_id=self.session.target, messages=nodelist)

    async def delete(self):
        try:
            if isinstance(self.session.message, list):
                for x in self.session.message:
                    await bot.call_action('delete_msg', message_id=x['message_id'])
            else:
                print(self.session.message)
                await bot.call_action('delete_msg', message_id=self.session.message['message_id'])
        except Exception:
            traceback.print_exc()

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            if self.msg.target.targetFrom == 'QQ|Group':
                await bot.send_group_msg(group_id=self.msg.session.target, message=f'[CQ:poke,qq={self.msg.session.sender}]')
            #await bot.answer_chat_action(self.msg.session.target, 'typing')
            pass

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
    async def fetch_target_list(targetList: list) -> List[MessageSession]:
        lst = []
        group_list_raw = await bot.call_action('get_group_list')
        group_list = []
        for g in group_list_raw:
            group_list.append(g['group_id'])
        friend_list_raw = await bot.call_action('get_friend_list')
        friend_list = []
        for f in friend_list_raw:
            friend_list.append(f)
        for x in targetList:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                if fet.target.targetFrom == 'QQ|Group':
                    if fet.session.target not in group_list:
                        continue
                if fet.target.targetFrom == 'QQ':
                    if fet.session.target not in friend_list:
                        continue
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[MessageSession] = None):
        send_list = []
        if user_list is not None:
            for x in user_list:
                try:
                    send = await x.sendMessage(message, quote=False)
                    send_list.append(send)
                except Exception:
                    traceback.print_exc()
        else:
            get_target_id = BotDBUtil.Module.get_enabled_this(module_name)
            group_list_raw = await bot.call_action('get_group_list')
            group_list = []
            for g in group_list_raw:
                group_list.append(g['group_id'])
            friend_list_raw = await bot.call_action('get_friend_list')
            friend_list = []
            for f in friend_list_raw:
                friend_list.append(f)
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x)
                if fetch:
                    if fetch.target.targetFrom == 'QQ|Group':
                        if fetch.session.target not in group_list:
                            continue
                    if fetch.target.targetFrom == 'QQ':
                        if fetch.session.target not in friend_list:
                            continue
                    try:
                        send = await fetch.sendMessage(message, quote=False)
                        send_list.append(send)
                        await asyncio.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
        return send_list
