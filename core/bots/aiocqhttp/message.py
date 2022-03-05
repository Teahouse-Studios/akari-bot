import asyncio
import html
import re
import traceback
from pathlib import Path
from typing import List, Union

import aiocqhttp.exceptions
from aiocqhttp import MessageSegment

from core.bots.aiocqhttp.client import bot
from core.bots.aiocqhttp.message_guild import MessageSession as MessageSessionGuild
from core.bots.aiocqhttp.tasks import MessageTaskManager, FinishedTasks
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session, Voice, FetchTarget as FT, \
    ExecutionLockList, FetchedSession as FS, FinishedSession as FinS
from core.elements.message.chain import MessageChain
from core.elements.others import confirm_command
from core.logger import Logger
from database import BotDBUtil


class FinishedSession(FinS):
    def __init__(self, result: list):
        self.result = result

    async def delete(self):
        """
        用于删除这条消息。
        """
        try:
            for x in self.result:
                await bot.call_action('delete_msg', message_id=x['message_id'])
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MS):
    class Feature:
        image = True
        voice = True
        embed = False
        forward = True
        delete = True
        wait = True
        quote = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False) -> FinishedSession:
        msg = MessageSegment.text('')
        if quote and self.target.targetFrom == 'QQ|Group' and self.session.message:
            msg = MessageSegment.reply(self.session.message.message_id)
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage('https://wdf.ink/6Oup')
        count = 0
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                msg = msg + MessageSegment.text(('\n' if count != 0 else '') + x.text)
            elif isinstance(x, Image):
                msg = msg + MessageSegment.image(Path(await x.get()).as_uri())
            elif isinstance(x, Voice):
                msg = msg + MessageSegment.record(file=Path(x.path).as_uri())
            count += 1
        Logger.info(f'[Bot] -> [{self.target.targetId}]: {msg}')
        if self.target.targetFrom == 'QQ|Group':
            try:
                send = await bot.send_group_msg(group_id=self.session.target, message=msg)
            except aiocqhttp.exceptions.ActionFailed:
                msg = msg + MessageSegment.text('（房蜂控）')
                send = await bot.send_group_msg(group_id=self.session.target, message=msg)
        else:
            send = await bot.send_private_msg(user_id=self.session.target, message=msg)
        return FinishedSession([send])

    async def waitConfirm(self, msgchain=None, quote=True):
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = MessageChain(msgchain)
            msgchain.append(Plain('（发送“是”或符合确认条件的词语来确认）'))
            send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_task(self.session.sender, flag)
        await flag.wait()
        if send is not None:
            await send.delete()
        if self.asDisplay(FinishedTasks.get()[self.session.sender]) in confirm_command:
            return True
        return False

    async def checkPermission(self):
        if self.target.targetFrom == 'QQ' \
            or self.target.senderInfo.check_TargetAdmin(self.target.targetId) \
            or self.target.senderInfo.query.isSuperUser:
            return True
        get_member_info = await bot.call_action('get_group_member_info', group_id=self.session.target,
                                                user_id=self.session.sender)
        if get_member_info['role'] in ['owner', 'admin']:
            return True
        return False

    async def checkNativePermission(self):
        if self.target.targetFrom == 'QQ':
            return True
        get_member_info = await bot.call_action('get_group_member_info', group_id=self.session.target,
                                                user_id=self.session.sender)
        if get_member_info['role'] in ['owner', 'admin']:
            return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    def asDisplay(self, message=None):
        return ''.join(
            re.split(r'\[CQ:.*?]', html.unescape(self.session.message.message if message is None else message)))

    async def fake_forward_msg(self, nodelist):
        if self.target.targetFrom == 'QQ|Group':
            await bot.call_action('send_group_forward_msg', group_id=int(self.session.target), messages=nodelist)

    async def sleep(self, s):
        ExecutionLockList.remove(self)
        await asyncio.sleep(s)

    async def delete(self):
        try:
            if isinstance(self.session.message, list):
                for x in self.session.message:
                    await bot.call_action('delete_msg', message_id=x['message_id'])
            else:
                await bot.call_action('delete_msg', message_id=self.session.message['message_id'])
        except Exception:
            Logger.error(traceback.format_exc())

    async def call_api(self, action, **params):
        return await bot.call_action(action, **params)

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            """if self.msg.target.targetFrom == 'QQ|Group':
                await bot.send_group_msg(group_id=self.msg.session.target,
                                         message=f'[CQ:poke,qq={self.msg.session.sender}]')"""
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(FS):
    def __init__(self, targetFrom, targetId):
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{targetFrom}|{targetId}',
                              targetFrom=targetFrom,
                              senderFrom=targetFrom,
                              senderName='')
        self.session = Session(message=False, target=targetId, sender=targetId)
        if targetFrom == 'QQ|Guild':
            self.parent = MessageSessionGuild(self.target, self.session)
        else:
            self.parent = MessageSession(self.target, self.session)


class FetchTarget(FT):
    name = 'QQ'

    @staticmethod
    async def fetch_target(targetId) -> Union[FetchedSession, bool]:
        matchTarget = re.match(r'^(QQ\|Group|QQ\|Guild|QQ)\|(.*)', targetId)
        if matchTarget:
            return FetchedSession(matchTarget.group(1), matchTarget.group(2))
        return False

    @staticmethod
    async def fetch_target_list(targetList: list) -> List[FetchedSession]:
        lst = []
        group_list_raw = await bot.call_action('get_group_list')
        group_list = []
        for g in group_list_raw:
            group_list.append(g['group_id'])
        friend_list_raw = await bot.call_action('get_friend_list')
        friend_list = []
        guild_list_raw = await bot.call_action('get_guild_list')
        guild_list = []
        for g in guild_list_raw:
            get_channel_list = await bot.call_action('get_guild_channel_list', guild_id=g['guild_id'])
            for channel in get_channel_list:
                if channel['channel_type'] == 1:
                    guild_list.append(f"{str(g['guild_id'])}|{str(channel['channel_id'])}")
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
                if fet.target.targetFrom == 'QQ|Guild':
                    if fet.session.target not in guild_list:
                        continue
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[FetchedSession] = None):
        send_list = []
        if user_list is not None:
            for x in user_list:
                try:
                    send = await x.sendDirectMessage(message)
                    send_list.append(send)
                except Exception:
                    Logger.error(traceback.format_exc())
        else:
            get_target_id = BotDBUtil.Module.get_enabled_this(module_name)
            group_list_raw = await bot.call_action('get_group_list')
            group_list = []
            for g in group_list_raw:
                group_list.append(g['group_id'])
            friend_list_raw = await bot.call_action('get_friend_list')
            friend_list = []
            for f in friend_list_raw:
                friend_list.append(f['user_id'])
            guild_list_raw = await bot.call_action('get_guild_list')
            guild_list = []
            for g in guild_list_raw:
                get_channel_list = await bot.call_action('get_guild_channel_list', guild_id=g['guild_id'],
                                                         no_cache=True)
                for channel in get_channel_list:
                    if channel['channel_type'] == 1:
                        guild_list.append(f"{str(g['guild_id'])}|{str(channel['channel_id'])}")
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x)
                Logger.info(fetch)
                if fetch:
                    if fetch.target.targetFrom == 'QQ|Group':
                        if int(fetch.session.target) not in group_list:
                            continue
                    if fetch.target.targetFrom == 'QQ':
                        if int(fetch.session.target) not in friend_list:
                            continue
                    if fetch.target.targetFrom == 'QQ|Guild':
                        if fetch.session.target not in guild_list:
                            continue
                    try:
                        print(fetch)
                        send = await fetch.sendDirectMessage(message)
                        send_list.append(send)
                        await asyncio.sleep(0.5)
                    except Exception:
                        Logger.error(traceback.format_exc())
        return send_list
