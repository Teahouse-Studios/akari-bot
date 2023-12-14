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

from bots.lagrange.client import bot
from bots.lagrange.info import client_name
from config import Config
from core.builtins import Bot, base_superuser_list, command_prefix, ErrorMessage, Image, Plain, Temp, Voice, \
    MessageTaskManager
from core.builtins.message import MessageSession as MessageSessionT
from core.builtins.message.chain import MessageChain
from core.exceptions import SendMessageFailed
from core.logger import Logger
from core.types import FetchTarget as FetchTargetT, FinishedSession as FinS
from core.utils.image import msgchain2image
from core.utils.storedata import get_stored_list
from database import BotDBUtil

enable_analytics = Config('enable_analytics')


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        if self.session.target.target_from in ['QQ|Group', 'QQ']:
            try:
                for x in self.message_id:
                    if x != 0:
                        await bot.call_action('delete_msg', message_id=x)
            except Exception:
                Logger.error(traceback.format_exc())


last_send_typing_time = {}
Temp.data['is_group_message_blocked'] = False
Temp.data['waiting_for_send_group_message'] = []


async def resending_group_message():
    falied_list = []
    try:
        if targets := Temp.data['waiting_for_send_group_message']:
            for x in targets:
                try:
                    if x['i18n']:
                        await x['fetch'].send_direct_message(x['fetch'].parent.locale.t(x['message'], **x['kwargs']))
                    else:
                        await x['fetch'].send_direct_message(x['message'])
                    Temp.data['waiting_for_send_group_message'].remove(x)
                    await asyncio.sleep(30)
                except SendMessageFailed:
                    Logger.error(traceback.format_exc())
                    falied_list.append(x)
                    if len(falied_list) > 3:
                        raise SendMessageFailed
        Temp.data['is_group_message_blocked'] = False
    except SendMessageFailed:
        Logger.error(traceback.format_exc())
        Temp.data['is_group_message_blocked'] = True
        for bu in base_superuser_list:
            fetch_base_superuser = await FetchTarget.fetch_target(bu)
            if fetch_base_superuser:
                await fetch_base_superuser. \
                    send_direct_message(fetch_base_superuser.parent.locale.t("error.message.paused",
                                                                             prefix=command_prefix[0]))


class MessageSession(MessageSessionT):
    class Feature:
        image = True
        voice = False
        embed = False
        forward = False
        delete = True
        wait = True
        quote = False

    async def send_message(self, message_chain, quote=True, disable_secret_check=False,
                           allow_split_image=True,
                           callback=None) -> FinishedSession:
        msg = []
        """
        if quote and self.target.target_from == 'QQ|Group' and self.session.message:
            msg = MessageSegment.reply(self.session.message.message_id)
        """
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(message_chain)
        count = 0
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, Plain):
                msg.append({
                    "type": "text",
                    "data": {
                        "text": ('\n' if count != 0 else '') + x.text
                    }
                })
            elif isinstance(x, Image):
                msg.append({
                    "type": "image",
                    "data": {
                        "file": "base64://" + await x.get_base64()
                    }
                })
            count += 1
        Logger.info(f'[Bot] -> [{self.target.target_id}]: {msg}')
        if self.target.target_from == 'QQ|Group':
            try:
                send = await bot.send_group_msg(group_id=int(self.session.target), message=msg)
            except aiocqhttp.exceptions.NetworkError:
                send = await bot.send_group_msg(group_id=int(self.session.target), message=MessageSegment.text(
                    self.locale.t("error.message.timeout")))
            except aiocqhttp.exceptions.ActionFailed:
                message_chain.insert(0, Plain(self.locale.t("error.message.limited.msg2img")))
                msg2img = MessageSegment.image(Path(await msgchain2image(message_chain, self)).as_uri())
                try:
                    send = await bot.send_group_msg(group_id=int(self.session.target), message=msg2img)
                except aiocqhttp.exceptions.ActionFailed as e:
                    raise SendMessageFailed(e.result['wording'])

            if Temp.data['is_group_message_blocked']:
                asyncio.create_task(resending_group_message())

        elif self.target.target_from == 'QQ|Guild':
            match_guild = re.match(r'(.*)\|(.*)', self.session.target)
            send = await bot.call_action('send_guild_channel_msg', guild_id=int(match_guild.group(1)),
                                         channel_id=int(match_guild.group(2)), message=msg)
        else:
            try:
                send = await bot.send_private_msg(user_id=self.session.target, message=msg)
            except aiocqhttp.exceptions.ActionFailed as e:
                if self.session.message.detail_type == 'private' and self.session.message.sub_type == 'group':
                    return FinishedSession(self, 0, [{}])
                else:
                    raise e
        if callback:
            MessageTaskManager.add_callback(send['message_id'], callback)
        return FinishedSession(self, send['message_id'], [send])

    async def check_native_permission(self):
        if self.target.target_from == 'QQ':
            return True
        elif self.target.target_from == 'QQ|Group':
            get_member_info = await bot.call_action('get_group_member_info', group_id=self.session.target,
                                                    user_id=self.session.sender)
            if get_member_info['role'] in ['owner', 'admin']:
                return True
        elif self.target.target_from == 'QQ|Guild':
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

    def as_display(self, text_only=False):
        """m = html.unescape(self.session.message.message)
            if text_only:
                return ''.join(
                    re.split(r'\\[CQ:.*?]', m)).strip()
            m = re.sub(r'\\[CQ:at,qq=(.*?)]', r'QQ|\1', m)
            m = re.sub(r'\\[CQ:forward,id=(.*?)]', r'\\[Ke:forward,id=\1]', m)

            return ''.join(
                re.split(r'\\[CQ:.*?]', m)).strip()"""
        return self.session.message

    async def fake_forward_msg(self, nodelist):
        if self.target.target_from == 'QQ|Group':
            get_ = get_stored_list(Bot.FetchTarget, 'forward_msg')
            if not get_['status']:
                await self.send_message(self.locale.t("core.message.forward_msg.disabled"))
                raise
            await bot.call_action('send_group_forward_msg', group_id=int(self.session.target), messages=nodelist)

    async def delete(self):
        if self.target.target_from in ['QQ', 'QQ|Group']:
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

    async def to_message_chain(self):
        m = html.unescape(self.session.message.message)
        m = re.sub(r'\[CQ:at,qq=(.*?)]', r'QQ|\1', m)
        m = re.sub(r'\[CQ:forward,id=(.*?)]', r'\[Ke:forward,id=\1]', m)
        spl = re.split(r'(\[CQ:.*?])', m)
        lst = []
        for s in spl:
            if s == '':
                continue
            if s.startswith('[CQ:'):
                if s.startswith('[CQ:image'):
                    sspl = s.split(',')
                    for ss in sspl:
                        if ss.startswith('url='):
                            lst.append(Image(ss[4:-1]))
            else:
                lst.append(Plain(s))

        return MessageChain(lst)

    async def call_api(self, action, **params):
        return await bot.call_action(action, **params)

    sendMessage = send_message
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkNativePermission = check_native_permission

    class Typing:
        def __init__(self, msg: MessageSessionT):
            self.msg = msg

        async def __aenter__(self):
            """if self.msg.target.target_from == 'QQ|Group':
                if self.msg.session.sender in last_send_typing_time:
                    if datetime.datetime.now().timestamp() - last_send_typing_time[self.msg.session.sender] <= 3600:
                        return
                last_send_typing_time[self.msg.session.sender] = datetime.datetime.now().timestamp()
                await bot.send_group_msg(group_id=self.msg.session.target,
                                         message=f'[CQ:poke,qq={self.msg.session.sender}]')"""

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> Union[Bot.FetchedSession]:
        match_target = re.match(r'^(QQ\|Group|QQ\|Guild|QQ)\|(.*)', target_id)
        if match_target:
            target_from = sender_from = match_target.group(1)
            target_id = match_target.group(2)
            if sender_id:
                match_sender = re.match(r'^(QQ\|Tiny|QQ)\|(.*)', sender_id)
                if match_sender:
                    sender_from = match_sender.group(1)
                    sender_id = match_sender.group(2)
            else:
                sender_id = target_id

            return Bot.FetchedSession(target_from, target_id, sender_from, sender_id)

    @staticmethod
    async def fetch_target_list(target_list: list) -> List[Bot.FetchedSession]:
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
        for x in target_list:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                if fet.target.target_from == 'QQ|Group':
                    if fet.session.target not in group_list:
                        continue
                if fet.target.target_from == 'QQ':
                    if fet.session.target not in friend_list:
                        continue
                if fet.target.target_from == 'QQ|Guild':
                    if fet.session.target not in guild_list:
                        continue
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[Bot.FetchedSession] = None, i18n=False, **kwargs):
        _tsk = []
        blocked = False

        async def post_(fetch_: Bot.FetchedSession):
            nonlocal _tsk
            nonlocal blocked
            try:
                if Temp.data['is_group_message_blocked'] and fetch_.target.target_from == 'QQ|Group':
                    Temp.data['waiting_for_send_group_message'].append({'fetch': fetch_, 'message': message,
                                                                        'i18n': i18n, 'kwargs': kwargs})
                else:
                    if i18n:
                        await fetch_.send_direct_message(fetch_.parent.locale.t(message, **kwargs))

                    else:
                        await fetch_.send_direct_message(message)
                    if _tsk:
                        _tsk = []
                if enable_analytics:
                    BotDBUtil.Analytics(fetch_).add('', module_name, 'schedule')
                await asyncio.sleep(0.5)
            except SendMessageFailed as e:
                if e.args[0] == 'send group message failed: blocked by server':
                    if len(_tsk) >= 3:
                        blocked = True
                    if not blocked:
                        _tsk.append({'fetch': fetch_, 'message': message, 'i18n': i18n, 'kwargs': kwargs})
                    else:
                        Temp.data['is_group_message_blocked'] = True
                        Temp.data['waiting_for_send_group_message'].append({'fetch': fetch_, 'message': message,
                                                                            'i18n': i18n, 'kwargs': kwargs})
                        if _tsk:
                            for t in _tsk:
                                Temp.data['waiting_for_send_group_message'].append(t)
                            _tsk = []
                        for bu in base_superuser_list:
                            fetch_base_superuser = await FetchTarget.fetch_target(bu)
                            if fetch_base_superuser:
                                await fetch_base_superuser. \
                                    send_direct_message(fetch_base_superuser.parent.locale.t("error.message.paused",
                                                                                             prefix=command_prefix[0]))
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
                    if fetch.target.target_from == 'QQ|Group':
                        if int(fetch.session.target) not in group_list:
                            continue
                    if fetch.target.target_from == 'QQ':
                        if int(fetch.session.target) not in friend_list:
                            continue
                    if fetch.target.target_from == 'QQ|Guild':
                        if fetch.session.target not in guild_list:
                            continue

                    if fetch.target.target_from in ['QQ', 'QQ|Guild']:
                        in_whitelist.append(post_(fetch))
                    else:
                        load_options: dict = json.loads(x.options)
                        if load_options.get('in_post_whitelist', False):
                            in_whitelist.append(post_(fetch))
                        else:
                            else_.append(post_(fetch))

            async def post_in_whitelist(lst):
                for l in lst:
                    await l
                    await asyncio.sleep(random.randint(1, 5))

            if in_whitelist:
                asyncio.create_task(post_in_whitelist(in_whitelist))

            async def post_not_in_whitelist(lst):
                for f in lst:
                    await f
                    await asyncio.sleep(random.randint(15, 30))

            if else_:
                asyncio.create_task(post_not_in_whitelist(else_))
                Logger.info(f"The task of posting messages to whitelisted groups is complete. "
                            f"Posting message to {len(else_)} groups not in whitelist.")


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
Bot.client_name = client_name
