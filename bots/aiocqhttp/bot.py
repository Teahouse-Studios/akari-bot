import html
import logging
import os
import re
import sys

import ujson as json
from aiocqhttp import Event
from datetime import datetime

from bots.aiocqhttp.client import bot
from bots.aiocqhttp.info import client_name
from bots.aiocqhttp.message import MessageSession, FetchTarget
from config import Config
from core.builtins import EnableDirtyWordCheck, PrivateAssets, Url, Temp
from core.scheduler import Scheduler, IntervalTrigger
from core.parser.message import parser
from core.tos import tos_report
from core.types import MsgInfo, Session
from core.utils.bot import load_prompt, init_async
from core.utils.info import Info
from core.utils.i18n import Locale
from database import BotDBUtil

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
EnableDirtyWordCheck.status = True if Config('enable_dirty_check') else False
Url.disable_mm = False if Config('enable_urlmanager') else True
qq_account = str(Config("qq_account"))
enable_listening_self_message = Config("qq_enable_listening_self_message")
lagrange_account = Config("lagrange_account")
lang = Config('locale')


@Scheduler.scheduled_job(IntervalTrigger(seconds=20))
async def check_lagrange_alive():
    if 'lagrange_keepalive' in Temp.data:
        Temp.data['lagrange_status'] = (datetime.now().timestamp() - Temp.data['lagrange_keepalive']) < 20


@bot.on_startup
async def startup():
    await init_async()
    bot.logger.setLevel(logging.WARNING)


@bot.on_websocket_connection
async def _(event: Event):
    await load_prompt(FetchTarget)


async def message_handler(event: Event):
    if event.detail_type == 'private':
        if event.sub_type == 'group':
            if Config('qq_disable_temp_session'):
                return await bot.send(event, Locale(lang).t('qq.message.disable_temp_session'))
    if event.user_id == lagrange_account:
        return
    filter_msg = re.match(r'.*?\[CQ:(?:json|xml).*?\].*?|.*?<\?xml.*?>.*?', event.message, re.MULTILINE | re.DOTALL)
    if filter_msg:
        match_json = re.match(r'.*?\[CQ:json,data=(.*?)\].*?', event.message, re.MULTILINE | re.DOTALL)
        if match_json:
            load_json = json.loads(html.unescape(match_json.group(1)))
            if load_json['app'] == 'com.tencent.multimsg':
                event.message = f'[CQ:forward,id={load_json["meta"]["detail"]["resid"]}]'
            else:
                return
        else:
            return
    reply_id = None
    match_reply = re.match(r'^\[CQ:reply,id=(-?\d+).*\].*', event.message)
    if match_reply:
        reply_id = int(match_reply.group(1))

    prefix = None
    if match_at := re.match(r'^\[CQ:at,qq=(\d+).*\](.*)', event.message):
        if match_at.group(1) == qq_account:
            event.message = match_at.group(2)
            if event.message in ['', ' ']:
                event.message = 'help'
            prefix = ['']

    target_id = 'QQ|' + (f'Group|{str(event.group_id)}' if event.detail_type == 'group' else str(event.user_id))

    msg = MessageSession(MsgInfo(target_id=target_id,
                                 sender_id=f'QQ|{str(event.user_id)}',
                                 target_from='QQ|Group' if event.detail_type == 'group' else 'QQ',
                                 sender_from='QQ', sender_name=event.sender['nickname'], client_name=client_name,
                                 message_id=event.message_id,
                                 reply_id=reply_id),
                         Session(message=event,
                                 target=event.group_id if event.detail_type == 'group' else event.user_id,
                                 sender=event.user_id))
    await parser(msg, running_mention=True, prefix=prefix)


if enable_listening_self_message:
    @bot.on('message_sent')
    async def _(event: Event):
        await message_handler(event)


@bot.on_message('group', 'private')
async def _(event: Event):
    await message_handler(event)


class GuildAccountInfo:
    tiny_id = None


@bot.on_message('guild')
async def _(event):
    if not GuildAccountInfo.tiny_id:
        profile = await bot.call_action('get_guild_service_profile')
        GuildAccountInfo.tiny_id = profile['tiny_id']
    tiny_id = event.user_id
    if tiny_id == GuildAccountInfo.tiny_id:
        return
    reply_id = None
    match_reply = re.match(r'^\[CQ:reply,id=(-?\d+).*\].*', event.message)
    if match_reply:
        reply_id = int(match_reply.group(1))
    target_id = f'QQ|Guild|{str(event.guild_id)}|{str(event.channel_id)}'
    msg = MessageSession(MsgInfo(target_id=target_id,
                                 sender_id=f'QQ|Tiny|{str(event.user_id)}',
                                 target_from='QQ|Guild',
                                 sender_from='QQ|Tiny', sender_name=event.sender['nickname'], client_name=client_name,
                                 message_id=event.message_id,
                                 reply_id=reply_id),
                         Session(message=event,
                                 target=f'{str(event.guild_id)}|{str(event.channel_id)}',
                                 sender=event.user_id))
    await parser(msg, running_mention=True)


@bot.on('request.friend')
async def _(event: Event):
    if BotDBUtil.SenderInfo('QQ|' + str(event.user_id)).query.isSuperUser:
        return {'approve': True}
    if not Config('qq_allow_approve_friend'):
        await bot.send_private_msg(user_id=event.user_id,
                                   message=Locale(lang).t('qq.message.disable_friend_request'))
    else:
        if BotDBUtil.SenderInfo('QQ|' + str(event.user_id)).query.isInBlockList:
            return {'approve': False}
        return {'approve': True}


@bot.on('request.group.invite')
async def _(event: Event):
    if BotDBUtil.SenderInfo('QQ|' + str(event.user_id)).query.isSuperUser:
        return {'approve': True}
    if not Config('qq_allow_approve_group_invite'):
        await bot.send_private_msg(user_id=event.user_id,
                                   message=Locale(lang).t('qq.message.disable_group_invite'))
    else:
        return {'approve': True}


@bot.on_notice('group_ban')
async def _(event: Event):
    if event.user_id == int(qq_account):
        result = BotDBUtil.UnfriendlyActions(target_id=event.group_id,
                                             sender_id=event.operator_id).add_and_check('mute', str(event.duration))
        if event.duration >= 259200:
            result = True
        if result:
            reason = Locale(lang).t('tos.message.reason.mute')
            await tos_report('QQ|' + str(event.operator_id), 'QQ|Group|' + str(event.group_id), reason, banned=True)
            BotDBUtil.GroupBlockList.add('QQ|Group|' + str(event.group_id))
            await bot.call_action('set_group_leave', group_id=event.group_id)
            BotDBUtil.SenderInfo('QQ|' + str(event.operator_id)).edit('isInBlockList', True)
            await bot.call_action('delete_friend', friend_id=event.operator_id)


@bot.on_notice('group_decrease')
async def _(event: Event):
    if event.sub_type == 'kick_me':
        result = True
        if result:
            reason = Locale(lang).t('tos.message.reason.kick')
            await tos_report('QQ|' + str(event.operator_id), 'QQ|Group|' + str(event.group_id), reason, banned=True)
            BotDBUtil.GroupBlockList.add('QQ|Group|' + str(event.group_id))
            BotDBUtil.SenderInfo('QQ|' + str(event.operator_id)).edit('isInBlockList', True)
            await bot.call_action('delete_friend', friend_id=event.operator_id)


@bot.on_message('group')
async def _(event: Event):
    result = BotDBUtil.GroupBlockList.check(f'QQ|Group|{str(event.group_id)}')
    if result:
        res = Locale(lang).t('tos.message.in_group_blocklist')
        if Config('issue_url'):
            res += '\n' + Locale(lang).t('tos.message.appeal', issue_url=Config('issue_url'))
        await bot.send(event=event, message=res)
        await bot.call_action('set_group_leave', group_id=event.group_id)


qq_host = Config("qq_host")
if qq_host:
    argv = sys.argv
    if 'subprocess' in sys.argv:
        Info.subprocess = True
    host, port = qq_host.split(':')
    bot.run(host=host, port=port, debug=False)
