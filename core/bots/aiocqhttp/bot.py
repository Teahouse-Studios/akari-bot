import asyncio
import logging
import os
import re

from aiocqhttp import Event

from config import Config
from core.bots.aiocqhttp.client import bot
from core.bots.aiocqhttp.message import MessageSession, FetchTarget
from core.bots.aiocqhttp.message_guild import MessageSession as MessageSessionGuild
from core.bots.aiocqhttp.tasks import MessageTaskManager, FinishedTasks
from core.elements import MsgInfo, Session, StartUp, Schedule, EnableDirtyWordCheck, PrivateAssets
from core.loader import ModulesManager
from core.parser.message import parser
from core.scheduler import Scheduler
from core.utils import init, load_prompt
from database import BotDBUtil
from database.logging_message import UnfriendlyActions

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
EnableDirtyWordCheck.status = True
init()


@bot.on_startup
async def startup():
    gather_list = []
    Modules = ModulesManager.return_modules_list_as_dict()
    for x in Modules:
        if isinstance(Modules[x], StartUp):
            gather_list.append(asyncio.ensure_future(Modules[x].function(FetchTarget)))
        elif isinstance(Modules[x], Schedule):
            Scheduler.add_job(func=Modules[x].function, trigger=Modules[x].trigger, args=[FetchTarget])
    await asyncio.gather(*gather_list)
    Scheduler.start()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    bot.logger.setLevel(logging.WARNING)


@bot.on_websocket_connection
async def _(event: Event):
    await load_prompt(FetchTarget)


@bot.on_message('group', 'private')
async def _(event: Event):
    if event.detail_type == 'private':
        if event.sub_type == 'group':
            return await bot.send(event, '请先添加好友后再进行命令交互。')
    filter_msg = re.match(r'.*?\[CQ:(?:json|xml).*?].*?|.*?<\?xml.*?>.*?', event.message)
    if filter_msg:
        return
    all_tsk = MessageTaskManager.get()
    user_id = event.user_id
    if user_id in all_tsk:
        FinishedTasks.add_task(user_id, event.message)
        all_tsk[user_id].set()
        MessageTaskManager.del_task(user_id)
    targetId = 'QQ|' + (f'Group|{str(event.group_id)}' if event.detail_type == 'group' else str(event.user_id))
    msg = MessageSession(MsgInfo(targetId=targetId,
                                 senderId=f'QQ|{str(event.user_id)}',
                                 targetFrom='QQ|Group' if event.detail_type == 'group' else 'QQ',
                                 senderFrom='QQ', senderName=''), Session(message=event,
                                                                          target=event.group_id if event.detail_type == 'group' else event.user_id,
                                                                          sender=event.user_id))
    await parser(msg)


class GuildAccountInfo:
    tiny_id = None


@bot.on_message('guild')
async def _(event):
    if GuildAccountInfo.tiny_id is None:
        profile = await bot.call_action('get_guild_service_profile')
        GuildAccountInfo.tiny_id = profile['tiny_id']
    tiny_id = event.user_id
    if tiny_id == GuildAccountInfo.tiny_id:
        return
    all_tsk = MessageTaskManager.guild_get()
    if tiny_id in all_tsk:
        FinishedTasks.add_guild_task(tiny_id, event.message)
        all_tsk[tiny_id].set()
        MessageTaskManager.del_guild_task(tiny_id)
    msg = MessageSessionGuild(MsgInfo(targetId=f'QQ|Guild|{str(event.guild_id)}|{str(event.channel_id)}',
                                      senderId=f'QQ|Tiny|{str(event.user_id)}',
                                      targetFrom='QQ|Guild',
                                      senderFrom='QQ|Tiny', senderName=''),
                              Session(message=event,
                                      target=f'{str(event.guild_id)}|{str(event.channel_id)}',
                                      sender=event.user_id))
    await parser(msg)


@bot.on('request.friend')
async def _(event: Event):
    if BotDBUtil.SenderInfo('QQ|' + str(event.user_id)).query.isInBlockList:
        return {'approve': False}
    return {'approve': True}


@bot.on('request.group.invite')
async def _(event: Event):
    await bot.send_private_msg(user_id=event.user_id,
                               message='你好！本机器人暂时不主动同意入群请求。\n'
                                       '请至https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=New&template=add_new_group.yaml&title=%5BNEW%5D%3A+申请入群。')


@bot.on_notice('group_ban')
async def _(event: Event):
    if event.user_id == int(Config("qq_account")):
        if event.duration >= 259200:
            result = True
        else:
            result = UnfriendlyActions(targetId=event.group_id,
                                       senderId=event.operator_id).add_and_check('mute', str(event.duration))
        if result:
            await bot.call_action('set_group_leave', group_id=event.group_id)
            BotDBUtil.SenderInfo('QQ|' + str(event.operator_id)).edit('isInBlockList', True)
            await bot.call_action('delete_friend', friend_id=event.operator_id)


"""
@bot.on_message('group')
async def _(event: Event):
    result = BotDBUtil.isGroupInAllowList(f'QQ|Group|{str(event.group_id)}')
    if not result:
        await bot.send(event=event, message='此群不在白名单中，已自动退群。'
                                            '\n如需申请白名单，请至https://github.com/Teahouse-Studios/bot/issues/new/choose发起issue。')
        await bot.call_action('set_group_leave', group_id=event.group_id)
"""

qq_host = Config("qq_host")
if qq_host:
    host, port = qq_host.split(':')
    bot.run(host=host, port=port, debug=False)
