import asyncio
import datetime
import html
import random
import re
import traceback
from pathlib import Path
from typing import List, Union

import aiocqhttp.exceptions
import ujson as json
from aiocqhttp import MessageSegment

from bots.aiocqhttp.client import bot
from config import Config
from core.builtins import Bot
from core.builtins import Plain, Image, Voice, Temp
from core.builtins.message import MessageSession as MS
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import MsgInfo, Session, FetchTarget as FT, \
    FetchedSession as FS, FinishedSession as FinS
from database import BotDBUtil

enable_analytics = Config('enable_analytics')
base_superuser = Config('base_superuser')


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        if self.session.target.targetFrom in ['QQ|Group', 'QQ']:
            try:
                for x in self.messageId:
                    await bot.call_action('delete_msg', message_id=x)
            except Exception:
                Logger.error(traceback.format_exc())


last_send_typing_time = {}
Temp.data['is_group_message_blocked'] = False
Temp.data['waiting_for_send_group_message'] = []


class MessageSession(MS):
    class Feature:
        image = True
        voice = True
        embed = False
        forward = True
        delete = True
        wait = True
        quote = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False,
                          allow_split_image=True) -> FinishedSession:
        msg = MessageSegment.text('')
        if quote and self.target.targetFrom == 'QQ|Group' and self.session.message:
            msg = MessageSegment.reply(self.session.message.message_id)
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage('https://wdf.ink/6Oup')
        self.sent.append(msgchain)
        count = 0
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                msg = msg + MessageSegment.text(('\n' if count != 0 else '') + x.text)
            elif isinstance(x, Image):
                msg = msg + MessageSegment.image(Path(await x.get()).as_uri())
            elif isinstance(x, Voice):
                if self.target.targetFrom != 'QQ|Guild':
                    msg = msg + MessageSegment.record(file=Path(x.path).as_uri())
            count += 1
        Logger.info(f'[Bot] -> [{self.target.targetId}]: {msg}')
        if self.target.targetFrom == 'QQ|Group':
            try:
                send = await bot.send_group_msg(group_id=self.session.target, message=msg)
            except aiocqhttp.exceptions.ActionFailed:
                anti_autofilter_word_list = ['（ffk）', '（阻止风向控制）', '（房蜂控）']
                msg = msg + MessageSegment.text(random.choice(anti_autofilter_word_list))
                send = await bot.send_group_msg(group_id=self.session.target, message=msg)
        elif self.target.targetFrom == 'QQ|Guild':
            match_guild = re.match(r'(.*)\|(.*)', self.session.target)
            send = await bot.call_action('send_guild_channel_msg', guild_id=int(match_guild.group(1)),
                                         channel_id=int(match_guild.group(2)), message=msg)
        else:
            send = await bot.send_private_msg(user_id=self.session.target, message=msg)
        return FinishedSession(self, send['message_id'], [send])

    async def checkPermission(self):
        if self.target.targetFrom == 'QQ' \
            or self.target.senderId in self.custom_admins \
            or self.target.senderInfo.query.isSuperUser:
            return True
        return await self.checkNativePermission()

    async def checkNativePermission(self):
        if self.target.targetFrom == 'QQ':
            return True
        elif self.target.targetFrom == 'QQ|Group':
            get_member_info = await bot.call_action('get_group_member_info', group_id=self.session.target,
                                                    user_id=self.session.sender)
            if get_member_info['role'] in ['owner', 'admin']:
                return True
        elif self.target.targetFrom == 'QQ|Guild':
            match_guild = re.match(r'(.*)\|(.*)', self.session.target)
            get_member_info = await bot.call_action('get_guild_member_profile', guild_id=match_guild.group(1),
                                                    user_id=self.session.sender)
            for m in get_member_info['roles']:
                if m['role_id'] == "2":
                    return True
            get_guild_info = await bot.call_action('get_guild_meta_by_guest', guild_id=match_guild.group(1))
            if get_guild_info['owner_id'] == self.session.sender:
                return True
            return False
        return False

    def asDisplay(self, text_only=False):
        m = html.unescape(self.session.message.message)
        if text_only:
            return ''.join(
                re.split(r'\[CQ:.*?]', m)).strip()
        m = re.sub(r'\[CQ:at,qq=(.*?)]', r'QQ|\1', m)
        m = re.sub(r'\[CQ:forward,id=(.*?)]', r'\[Ke:forward,id=\1]', m)

        return ''.join(
            re.split(r'\[CQ:.*?]', m)).strip()

    async def fake_forward_msg(self, nodelist):
        if self.target.targetFrom == 'QQ|Group':
            await bot.call_action('send_group_forward_msg', group_id=int(self.session.target), messages=nodelist)

    async def delete(self):
        if self.target.targetFrom in ['QQ', 'QQ|Group']:
            try:
                if isinstance(self.session.message, list):
                    for x in self.session.message:
                        await bot.call_action('delete_msg', message_id=x['message_id'])
                else:
                    await bot.call_action('delete_msg', message_id=self.session.message['message_id'])
            except Exception:
                Logger.error(traceback.format_exc())

    async def get_text_channel_list(self):
        match_guild = re.match(r'(.*)\|(.*)', self.session.target)
        get_channels_info = await bot.call_action('get_guild_channel_list', guild_id=match_guild.group(1),
                                                  no_cache=True)
        lst = []
        for m in get_channels_info:
            if m['channel_type'] == 1:
                lst.append(f'{m["owner_guild_id"]}|{m["channel_id"]}')
        return lst

    async def call_api(self, action, **params):
        return await bot.call_action(action, **params)

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            if self.msg.target.targetFrom == 'QQ|Group':
                if self.msg.session.sender in last_send_typing_time:
                    if datetime.datetime.now().timestamp() - last_send_typing_time[self.msg.session.sender] <= 3600:
                        return
                last_send_typing_time[self.msg.session.sender] = datetime.datetime.now().timestamp()
                await bot.send_group_msg(group_id=self.msg.session.target,
                                         message=f'[CQ:poke,qq={self.msg.session.sender}]')

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(FS):
    def __init__(self, targetFrom, targetId):
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{targetFrom}|{targetId}',
                              targetFrom=targetFrom,
                              senderFrom=targetFrom,
                              senderName='',
                              clientName='QQ',
                              messageId=0,
                              replyId=None)
        self.session = Session(message=False, target=targetId, sender=targetId)
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
        _tsk = []
        blocked = False

        async def post_(fetch_):
            nonlocal _tsk
            nonlocal blocked
            try:
                if Temp.data['is_group_message_blocked'] and fetch_.target.targetFrom == 'QQ|Group':
                    Temp.data['waiting_for_send_group_message'].append({'fetch': fetch_, 'message': message})
                else:
                    await fetch_.sendDirectMessage(message)
                    if _tsk:
                        _tsk = []
                if enable_analytics:
                    BotDBUtil.Analytics(fetch_).add('', module_name, 'schedule')
                await asyncio.sleep(0.5)
            except aiocqhttp.ActionFailed as e:
                if e.result['wording'] == 'send group message failed: blocked by server':
                    if len(_tsk) >= 3:
                        blocked = True
                    if not blocked:
                        _tsk.append({'fetch': fetch_, 'message': message})
                    else:
                        Temp.data['is_group_message_blocked'] = True
                        Temp.data['waiting_for_send_group_message'].append({'fetch': fetch_, 'message': message})
                        if _tsk:
                            for t in _tsk:
                                Temp.data['waiting_for_send_group_message'].append(t)
                            _tsk = []
                        fetch_base_superuser = await FetchTarget.fetch_target(base_superuser)
                        if fetch_base_superuser:
                            await fetch_base_superuser.sendDirectMessage(
                                '群消息发送被服务器拦截，已暂停群消息发送，使用~resume命令恢复推送。')
            except Exception:
                Logger.error(traceback.format_exc())

        if user_list is not None:
            for x in user_list:
                await post_(x)
        else:
            get_target_id = BotDBUtil.TargetInfo.get_enabled_this(module_name, "QQ")
            group_list_raw = await bot.call_action('get_group_list')
            group_list = [g['group_id'] for g in group_list_raw]
            friend_list_raw = await bot.call_action('get_friend_list')
            friend_list = [f['user_id'] for f in friend_list_raw]
            guild_list_raw = await bot.call_action('get_guild_list')
            guild_list = []
            for g in guild_list_raw:
                try:
                    get_channel_list = await bot.call_action('get_guild_channel_list', guild_id=g['guild_id'],
                                                             no_cache=True)
                    for channel in get_channel_list:
                        if channel['channel_type'] == 1:
                            guild_list.append(f"{str(g['guild_id'])}|{str(channel['channel_id'])}")
                except Exception:
                    traceback.print_exc()
                    continue

            in_whitelist = []
            else_ = []
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x.targetId)
                Logger.debug(fetch)
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

                    if fetch.target.targetFrom in ['QQ', 'QQ|Guild']:
                        in_whitelist.append(post_(fetch))
                    else:
                        load_options: dict = json.loads(x.options)
                        if load_options.get('in_post_whitelist', False):
                            in_whitelist.append(post_(fetch))
                        else:
                            else_.append(post_(fetch))

            if in_whitelist:
                for x in in_whitelist:
                    await x
                    await asyncio.sleep(random.randint(1, 5))

            async def post_not_in_whitelist(lst):
                for f in lst:
                    await f
                    await asyncio.sleep(random.randint(15, 30))

            if else_:
                asyncio.create_task(post_not_in_whitelist(else_))
                Logger.info(f"Post done. but there are still {len(else_)} processes running.")


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
