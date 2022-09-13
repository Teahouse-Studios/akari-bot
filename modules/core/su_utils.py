import asyncio
import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import ujson as json

from config import Config
from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import PrivateAssets, Image, Plain, ExecutionLockList
from core.loader import ModulesManager
from core.parser.message import remove_temp_ban
from core.tos import pardon_user, warn_user
from core.utils.cache import random_cache_path
from core.utils.tasks import MessageTaskManager
from database import BotDBUtil

su = on_command('superuser', alias=['su'], developers=['OasisAkari', 'Dianliang233'], required_superuser=True)


@su.handle('add <user>')
async def add_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if not user.startswith(f'{message.target.senderFrom}|'):
        await message.finish(f'ID格式错误，请对象使用{message.prefixes[0]}whoami命令查看用户ID。')
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', True):
            await message.finish('操作成功：已将' + user + '设置为超级用户。')


@su.handle('del <user>')
async def del_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if not user.startswith(f'{message.target.senderFrom}|'):
        await message.finish(f'ID格式错误，请对象使用{message.prefixes[0]}whoami命令查看用户ID。')
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', False):
            await message.finish('操作成功：已将' + user + '移出超级用户。')


ana = on_command('analytics', required_superuser=True)


@ana.handle()
async def _(msg: MessageSession):
    if Config('enable_analytics'):
        first_record = BotDBUtil.Analytics.get_first()
        get_counts = BotDBUtil.Analytics.get_count()
        await msg.finish(f'机器人已执行命令次数（自{str(first_record.timestamp)}开始统计）：{get_counts}')
    else:
        await msg.finish('机器人未开启命令统计功能。')


@ana.handle('days [<name>]')
async def _(msg: MessageSession):
    if Config('enable_analytics'):
        first_record = BotDBUtil.Analytics.get_first()
        module_ = None
        if '<name>' in msg.parsed_msg:
            module_ = msg.parsed_msg['<name>']
        data_ = {}
        for d in range(30):
            new = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1) - timedelta(days=30 - d - 1)
            old = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1) - timedelta(days=30 - d)
            get_ = BotDBUtil.Analytics.get_count_by_times(new, old, module_)
            data_[old.day] = get_
        data_x = []
        data_y = []
        for x in data_:
            data_x.append(str(x))
            data_y.append(data_[x])
        plt.plot(data_x, data_y, "-o")
        plt.plot(data_x[-1], data_y[-1], "-ro")
        plt.xlabel('Days')
        plt.ylabel('Counts')
        plt.tick_params(axis='x', labelrotation=45, which='major', labelsize=10)

        plt.gca().yaxis.get_major_locator().set_params(integer=True)
        for xitem, yitem in np.nditer([data_x, data_y]):
            plt.annotate(yitem, (xitem, yitem), textcoords="offset points", xytext=(0, 10), ha="center")
        path = random_cache_path() + '.png'
        plt.savefig(path)
        plt.close()
        await msg.finish(
            [Plain(
                f'最近30天的{module_ if module_ is not None else ""}命令调用次数统计（自{str(first_record.timestamp)}开始统计）：'),
                Image(path)])


set_ = on_command('set', required_superuser=True)


@set_.handle('modules <targetId> <modules> ...')
async def _(msg: MessageSession):
    target = msg.parsed_msg['<targetId>']
    if not target.startswith(f'{msg.target.targetFrom}|'):
        await msg.finish(f'ID格式错误。')
    target_data = BotDBUtil.TargetInfo(target)
    if target_data.query is None:
        wait_confirm = await msg.waitConfirm('该群未初始化，确认进行操作吗？')
        if not wait_confirm:
            return
    modules = [m for m in [msg.parsed_msg['<modules>']] + msg.parsed_msg.get('...', [])
               if m in ModulesManager.return_modules_list_as_dict(msg.target.targetFrom)]
    target_data.enable(modules)
    await msg.finish(f'成功为对象配置了以下模块：{", ".join(modules)}')


@set_.handle('option <targetId> <k> <v>')
async def _(msg: MessageSession):
    target = msg.parsed_msg['<targetId>']
    k = msg.parsed_msg['<k>']
    v = msg.parsed_msg['<v>']
    if not target.startswith(f'{msg.target.targetFrom}|'):
        await msg.finish(f'ID格式错误。')
    target_data = BotDBUtil.TargetInfo(target)
    if target_data.query is None:
        wait_confirm = await msg.waitConfirm('该群未初始化，确认进行操作吗？')
        if not wait_confirm:
            return
    if v.startswith(('[', '{')):
        v = json.loads(v)
    elif v == 'True':
        v = True
    elif v == 'False':
        v = False
    target_data.edit_option(k, v)
    await msg.finish(f'成功为对象设置了以下参数：{k} -> {str(v)}')


ae = on_command('abuse', alias=['ae'], developers=['Dianliang233'], required_superuser=True)


@ae.handle('check <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    warns = BotDBUtil.SenderInfo(user).query.warns
    await msg.finish(f'{user} 已被警告 {warns} 次。')


@ae.handle('warn <user> [<count>]')
async def _(msg: MessageSession):
    count = int(msg.parsed_msg.get('<count>', 1))
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    warn_count = await warn_user(user, count)
    await msg.finish(f'成功警告 {user} {count} 次。此用户已被警告 {warn_count} 次。')


@ae.handle('revoke <user> [<count>]')
async def _(msg: MessageSession):
    count = 0 - int(msg.parsed_msg.get('<count>', 1))
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    warn_count = await warn_user(user, count)
    await msg.finish(f'成功移除警告 {user} 的 {abs(count)} 次警告。此用户已被警告 {warn_count} 次。')


@ae.handle('clear <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    await pardon_user(user)
    await msg.finish(f'成功清除 {user} 的警告。')


@ae.handle('untempban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    await remove_temp_ban(user)
    await msg.finish(f'成功解除 {user} 的临时限制。')


@ae.handle('ban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', True):
        await msg.finish(f'成功封禁 {user}。')


@ae.handle('unban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', False):
        await msg.finish(f'成功解除 {user} 的封禁。')


rst = on_command('restart', developers=['OasisAkari'], required_superuser=True)


def restart():
    sys.exit(233)


def write_version_cache(msg: MessageSession):
    update = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
    write_version = open(update, 'w')
    write_version.write(json.dumps({'From': msg.target.targetFrom, 'ID': msg.target.targetId}))
    write_version.close()


restart_time = []


async def wait_for_restart(msg: MessageSession):
    get = ExecutionLockList.get()
    if datetime.now().timestamp() - restart_time[0] < 60:
        if len(get) != 0:
            await msg.sendMessage(f'有 {len(get)} 个命令正在执行中，将于执行完毕后重启。')
            await asyncio.sleep(10)
            return await wait_for_restart(msg)
        else:
            await msg.sendMessage('重启中...')
            get_wait_list = MessageTaskManager.get()
            for x in get_wait_list:
                for y in get_wait_list[x]:
                    if get_wait_list[x][y]['active']:
                        await get_wait_list[x][y]['original_session'].sendMessage('由于机器人正在重启，您此次执行命令的后续操作已被强制取消。'
                                                                                  '请稍后重新执行命令，对此带来的不便，我们深感抱歉。')

    else:
        await msg.sendMessage('等待已超时，强制重启中...')


@rst.handle()
async def restart_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        restart_time.append(datetime.now().timestamp())
        await wait_for_restart(msg)
        write_version_cache(msg)
        restart()


upd = on_command('update', developers=['OasisAkari'], required_superuser=True)


def pull_repo():
    return os.popen('git pull', 'r').read()[:-1]


@upd.handle()
async def update_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        await msg.sendMessage(pull_repo())


upds = on_command('update&restart', developers=['OasisAkari'], required_superuser=True)


@upds.handle()
async def update_and_restart_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        restart_time.append(datetime.now().timestamp())
        await wait_for_restart(msg)
        write_version_cache(msg)
        await msg.sendMessage(pull_repo())
        restart()


echo = on_command('echo', developers=['OasisAkari'], required_superuser=True)


@echo.handle('<display_msg>')
async def _(msg: MessageSession):
    await msg.finish(msg.parsed_msg['<display_msg>'])


say = on_command('say', developers=['OasisAkari'], required_superuser=True)


@say.handle('<display_msg>')
async def _(msg: MessageSession):
    await msg.finish(msg.parsed_msg['<display_msg>'], quote=False)


if Config('enable_eval'):
    _eval = on_command('eval', developers=['Dianliang233'], required_superuser=True)


    @_eval.handle('<display_msg>')
    async def _(msg: MessageSession):
        await msg.finish(str(eval(msg.parsed_msg['<display_msg>'], {'msg': msg})))
