import asyncio
import os
import re
import shutil
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import ujson as json
from dateutil.relativedelta import relativedelta

from config import Config, CFG
from core.builtins import Bot, PrivateAssets, Image, Plain, ExecutionLockList, Temp, MessageTaskManager
from core.component import module
from core.exceptions import TestException
from core.loader import ModulesManager
from core.logger import Logger
from core.parser.message import remove_temp_ban
from core.tos import pardon_user, warn_user
from core.utils.cache import random_cache_path
from core.utils.info import Info
from core.utils.storedata import get_stored_list, update_stored_list
from database import BotDBUtil


su = module('superuser', alias='su', required_superuser=True, base=True)


@su.command('add <UserID>')
async def add_su(msg: Bot.MessageSession):
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.superuser.invalid", target=msg.target.sender_from))
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', True):
            await msg.finish(msg.locale.t("success"))


@su.command('remove <UserID>')
async def del_su(msg: Bot.MessageSession):
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.superuser.invalid", target=msg.target.sender_from))
    if user == msg.target.sender_id:
        confirm = await msg.wait_confirm(msg.locale.t("core.message.admin.remove.confirm"), append_instruction=False)
        if not confirm:
            await msg.finish()
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', False):
            await msg.finish(msg.locale.t("success"))


ana = module('analytics', required_superuser=True, base=True)


@ana.command()
async def _(msg: Bot.MessageSession):
    if Config('enable_analytics'):
        first_record = BotDBUtil.Analytics.get_first()
        get_counts = BotDBUtil.Analytics.get_count()

        new = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        old = datetime.now().replace(hour=0, minute=0, second=0)
        get_counts_today = BotDBUtil.Analytics.get_count_by_times(new, old)

        await msg.finish(msg.locale.t("core.message.analytics.counts", first_record=first_record.timestamp,
                                      counts=get_counts, counts_today=get_counts_today))
    else:
        await msg.finish(msg.locale.t("core.message.analytics.disabled"))


@ana.command('days [<name>]')
async def _(msg: Bot.MessageSession):
    if Config('enable_analytics'):
        first_record = BotDBUtil.Analytics.get_first()
        module_ = None
        if '<name>' in msg.parsed_msg:
            module_ = msg.parsed_msg['<name>']
        if not module_:
            result = msg.locale.t("core.message.analytics.days.total", first_record=first_record.timestamp)
        else:
            result = msg.locale.t("core.message.analytics.days", module=module_,
                                  first_record=first_record.timestamp)
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
        await msg.finish([Plain(result), Image(path)])


@ana.command('year [<name>]')
async def _(msg: Bot.MessageSession):
    if Config('enable_analytics'):
        first_record = BotDBUtil.Analytics.get_first()
        module_ = None
        if '<name>' in msg.parsed_msg:
            module_ = msg.parsed_msg['<name>']
        if not module_:
            result = msg.locale.t("core.message.analytics.year.total", first_record=first_record.timestamp)
        else:
            result = msg.locale.t("core.message.analytics.year", module=module_,
                                  first_record=first_record.timestamp)
        data_ = {}
        for d in range(12):
            new = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0) + \
                relativedelta(years=1) - relativedelta(months=12 - d - 1)
            old = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0) + \
                relativedelta(years=1) - relativedelta(months=12 - d)
            get_ = BotDBUtil.Analytics.get_count_by_times(new, old, module_)
            data_[old.month] = get_
        data_x = []
        data_y = []
        for x in data_:
            data_x.append(str(x))
            data_y.append(data_[x])
        plt.plot(data_x, data_y, "-o")
        plt.plot(data_x[-1], data_y[-1], "-ro")
        plt.xlabel('Months')
        plt.ylabel('Counts')
        plt.tick_params(axis='x', labelrotation=45, which='major', labelsize=10)

        plt.gca().yaxis.get_major_locator().set_params(integer=True)
        for xitem, yitem in np.nditer([data_x, data_y]):
            plt.annotate(yitem, (xitem, yitem), textcoords="offset points", xytext=(0, 10), ha="center")
        path = random_cache_path() + '.png'
        plt.savefig(path)
        plt.close()
        await msg.finish([Plain(result), Image(path)])


purge = module('purge', required_superuser=True, base=True)


@purge.command()
async def _(msg: Bot.MessageSession):
    cache_path = os.path.abspath(Config('cache_path'))
    if os.path.exists(cache_path):
        if os.listdir(cache_path):
            shutil.rmtree(cache_path)
            os.mkdir(cache_path)
            await msg.finish(msg.locale.t("core.message.purge.success"))
        else:
            await msg.finish(msg.locale.t("core.message.purge.empty"))
    else:
        os.mkdir(cache_path)
        await msg.finish(msg.locale.t("core.message.purge.empty"))


set_ = module('set', required_superuser=True, base=True)


@set_.command('modules <target_id> <modules> ...')
async def _(msg: Bot.MessageSession):
    target = msg.parsed_msg['<target_id>']
    if not target.startswith(f'{msg.target.target_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    target_data = BotDBUtil.TargetInfo(target)
    if not target_data.query:
        confirm = await msg.wait_confirm(msg.locale.t("core.message.set.confirm.init"), append_instruction=False)
        if not confirm:
            await msg.finish()
    modules = [m for m in [msg.parsed_msg['<modules>']] + msg.parsed_msg.get('...', [])
               if m in ModulesManager.return_modules_list(msg.target.target_from)]
    target_data.enable(modules)
    await msg.finish(msg.locale.t("core.message.set.module.success") + ", ".join(modules))


@set_.command('option <target_id> <k> <v>')
async def _(msg: Bot.MessageSession):
    target = msg.parsed_msg['<target_id>']
    k = msg.parsed_msg['<k>']
    v = msg.parsed_msg['<v>']
    if not target.startswith(f'{msg.target.target_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    target_data = BotDBUtil.TargetInfo(target)
    if not target_data.query:
        confirm = await msg.wait_confirm(msg.locale.t("core.message.set.confirm.init"), append_instruction=False)
        if not confirm:
            await msg.finish()
    if v.startswith(('[', '{')):
        v = json.loads(v)
    elif v.upper() == 'TRUE':
        v = True
    elif v.upper() == 'FALSE':
        v = False
    target_data.edit_option(k, v)
    await msg.finish(msg.locale.t("core.message.set.help.option.success", k=k, v=v))


ae = module('abuse', alias='ae', required_superuser=True, base=True)


@ae.command('check <user>')
async def _(msg: Bot.MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    warns = BotDBUtil.SenderInfo(user).query.warns
    await msg.finish(msg.locale.t("core.message.abuse.check.warns", user=user, warns=warns))


@ae.command('warn <user> [<count>]')
async def _(msg: Bot.MessageSession):
    count = int(msg.parsed_msg.get('<count>', 1))
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    warn_count = await warn_user(user, count)
    await msg.finish(msg.locale.t("core.message.abuse.warn.success", user=user, counts=count, warn_counts=warn_count))


@ae.command('revoke <user> [<count>]')
async def _(msg: Bot.MessageSession):
    count = 0 - int(msg.parsed_msg.get('<count>', 1))
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    warn_count = await warn_user(user, count)
    await msg.finish(msg.locale.t("core.message.abuse.revoke.success", user=user, counts=count, warn_counts=warn_count))


@ae.command('clear <user>')
async def _(msg: Bot.MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    await pardon_user(user)
    await msg.finish(msg.locale.t("core.message.abuse.clear.success", user=user))


@ae.command('untempban <user>')
async def _(msg: Bot.MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    await remove_temp_ban(user)
    await msg.finish(msg.locale.t("core.message.abuse.untempban.success", user=user))


@ae.command('ban <user>')
async def _(msg: Bot.MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', True):
        await msg.finish(msg.locale.t("core.message.abuse.ban.success", user=user))


@ae.command('unban <user>')
async def _(msg: Bot.MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("core.message.set.invalid"))
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', False):
        await msg.finish(msg.locale.t("core.message.abuse.unban.success", user=user))


upd = module('update', required_superuser=True, base=True)


def pull_repo():
    pull_repo_result = os.popen('git pull', 'r').read()[:-1]
    if pull_repo_result == '':
        return False
    return pull_repo_result


def update_dependencies():
    poetry_install = os.popen('poetry install').read()[:-1]
    if poetry_install != '':
        return poetry_install
    pip_install = os.popen('pip install -r requirements.txt').read()[:-1]
    if len(pip_install) > 500:
        return '...' + pip_install[-500:]
    return pip_install


@upd.command()
async def update_bot(msg: Bot.MessageSession):
    confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False)
    if confirm:
        pull_repo_result = pull_repo()
        if pull_repo_result:
            await msg.send_message(pull_repo_result)
        else:
            await msg.send_message(msg.locale.t("core.message.update.failed"))
        await msg.finish(update_dependencies())
    else:
        await msg.finish()

if Info.subprocess:
    rst = module('restart', required_superuser=True, base=True)

    def restart():
        sys.exit(233)

    def write_version_cache(msg: Bot.MessageSession):
        update = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
        write_version = open(update, 'w')
        write_version.write(json.dumps({'From': msg.target.target_from, 'ID': msg.target.target_id}))
        write_version.close()

    restart_time = []

    async def wait_for_restart(msg: Bot.MessageSession):
        get = ExecutionLockList.get()
        if datetime.now().timestamp() - restart_time[0] < 60:
            if len(get) != 0:
                await msg.send_message(msg.locale.t("core.message.restart.wait", count=len(get)))
                await asyncio.sleep(10)
                return await wait_for_restart(msg)
            else:
                await msg.send_message(msg.locale.t("core.message.restart.restarting"))
                get_wait_list = MessageTaskManager.get()
                for x in get_wait_list:
                    for y in get_wait_list[x]:
                        for z in get_wait_list[x][y]:
                            if get_wait_list[x][y][z]['active']:
                                await z.send_message(z.locale.t("core.message.restart.prompt"))

        else:
            await msg.send_message(msg.locale.t("core.message.restart.timeout"))

    @rst.command()
    async def restart_bot(msg: Bot.MessageSession):
        confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False)
        if confirm:
            restart_time.append(datetime.now().timestamp())
            await wait_for_restart(msg)
            write_version_cache(msg)
            restart()
        else:
            await msg.finish()


if Info.subprocess:
    upds = module('update&restart', required_superuser=True, alias='u&r', base=True)

    @upds.command()
    async def update_and_restart_bot(msg: Bot.MessageSession):
        confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False)
        if confirm:
            restart_time.append(datetime.now().timestamp())
            await wait_for_restart(msg)
            write_version_cache(msg)
            pull_repo_result = pull_repo()
            if pull_repo_result != '':
                await msg.send_message(pull_repo_result)
                await msg.send_message(update_dependencies())
            else:
                Logger.warn(f'Failed to get Git repository result.')
                await msg.send_message(msg.locale.t("core.message.update.failed"))
            restart()
        else:
            await msg.finish()


if Bot.FetchTarget.name == 'QQ':
    resume = module('resume', required_base_superuser=True)

    @resume.command()
    async def resume_sending_group_message(msg: Bot.MessageSession):
        Temp.data['is_group_message_blocked'] = False
        if targets := Temp.data['waiting_for_send_group_message']:
            await msg.send_message(msg.locale.t("core.message.resume.processing", counts=len(targets)))
            for x in targets:
                if x['i18n']:
                    await x['fetch'].send_direct_message(x['fetch'].parent.locale.t(x['message'], **x['kwargs']))
                else:
                    await x['fetch'].send_direct_message(x['message'])
                Temp.data['waiting_for_send_group_message'].remove(x)
                await asyncio.sleep(30)
            await msg.finish(msg.locale.t("core.message.resume.done"))
        else:
            await msg.finish(msg.locale.t("core.message.resume.nothing"))

    @resume.command('continue')
    async def resume_sending_group_message(msg: Bot.MessageSession):
        if not Temp.data['waiting_for_send_group_message']:
            await msg.finish(msg.locale.t("core.message.resume.nothing"))

        del Temp.data['waiting_for_send_group_message'][0]
        Temp.data['is_group_message_blocked'] = False
        if targets := Temp.data['waiting_for_send_group_message']:
            await msg.send_message(msg.locale.t("core.message.resume.skip", counts=len(targets)))
            for x in targets:
                if x['i18n']:
                    await x['fetch'].send_direct_message(x['fetch'].parent.locale.t(x['message']))
                else:
                    await x['fetch'].send_direct_message(x['message'])
                Temp.data['waiting_for_send_group_message'].remove(x)
                await asyncio.sleep(30)
            await msg.finish(msg.locale.t("core.message.resume.done"))
        else:
            await msg.finish(msg.locale.t("core.message.resume.nothing"))

    @resume.command('clear')
    async def _(msg: Bot.MessageSession):
        Temp.data['is_group_message_blocked'] = False
        Temp.data['waiting_for_send_group_message'] = []
        await msg.finish(msg.locale.t("core.message.resume.clear"))

    forward_msg = module('forward_msg', required_superuser=True, base=True)

    @forward_msg.command()
    async def _(msg: Bot.MessageSession):
        alist = get_stored_list(Bot.FetchTarget, 'forward_msg')
        if not alist:
            alist = {'status': True}
        alist['status'] = not alist['status']
        update_stored_list(Bot.FetchTarget, 'forward_msg', alist)
        if alist['status']:
            await msg.finish(msg.locale.t('core.message.forward_msg.enable'))
        else:
            await msg.finish(msg.locale.t('core.message.forward_msg.disable'))


echo = module('echo', required_superuser=True, base=True)


@echo.command('<display_msg>')
async def _(msg: Bot.MessageSession):
    await msg.finish(msg.parsed_msg['<display_msg>'])


say = module('say', required_superuser=True, base=True)


@say.command('<display_msg>')
async def _(msg: Bot.MessageSession):
    await msg.finish(msg.parsed_msg['<display_msg>'], quote=False)


rse = module('raise', required_superuser=True, base=True)


@rse.command()
async def _(msg: Bot.MessageSession):
    e = msg.locale.t("core.message.raise")
    raise TestException(e)


if Config('enable_eval'):
    _eval = module('eval', required_superuser=True, base=True)

    @_eval.command('<display_msg>')
    async def _(msg: Bot.MessageSession):
        await msg.finish(str(eval(msg.parsed_msg['<display_msg>'], {'msg': msg})))


cfg_ = module('config', required_superuser=True, alias='cfg', base=True)


def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False


def isint(num):
    try:
        int(num)
        return True
    except ValueError:
        return False


@cfg_.command('write <k> <v> [-s]')
async def _(msg: Bot.MessageSession):
    value = msg.parsed_msg['<v>']
    if value.lower() == 'true':
        value = True
    elif value.lower() == 'false':
        value = False
    elif isint(value):
        value = int(value)
    elif isfloat(value):
        value = float(value)
    elif re.match(r'^\[.*\]$', value):
        try:
            value = json.loads(value)
        except BaseException:
            await msg.finish(msg.locale.t("core.message.config.write.failed"))

    CFG.write(msg.parsed_msg['<k>'], value, msg.parsed_msg['-s'])
    await msg.finish(msg.locale.t("success"))


@cfg_.command('delete <k>')
async def _(msg: Bot.MessageSession):
    if CFG.delete(msg.parsed_msg['<k>']):
        await msg.finish(msg.locale.t("success"))
    else:
        await msg.finish(msg.locale.t("failed"))


if Config('openai_api_key'):
    petal = module('petal', base=True, alias='petals')

    @petal.command()
    async def _(msg: Bot.MessageSession):
        await msg.finish(msg.locale.t('core.message.petal.self', petal=msg.data.petal))

    @petal.command('[<target>] {{core.help.petal}}', required_superuser=True)
    async def _(msg: Bot.MessageSession):
        group = msg.parsed_msg['<target>']
        target = BotDBUtil.TargetInfo(group)
        await msg.finish(msg.locale.t('core.message.petal', target=group, petal=target.petal))

    @petal.command('modify <petal> [<target>]', required_superuser=True)
    async def _(msg: Bot.MessageSession):
        petal = msg.parsed_msg['<petal>']
        if '<target>' in msg.parsed_msg:
            group = msg.parsed_msg['<target>']
            target = BotDBUtil.TargetInfo(group)
            target.modify_petal(int(petal))
            await msg.finish(
                msg.locale.t('core.message.petal.modify', target=group, add_petal=petal, petal=target.petal))
        else:
            target = msg.data
            target.modify_petal(int(petal))
            await msg.finish(msg.locale.t('core.message.petal.modify.self', add_petal=petal, petal=target.petal))

    @petal.command('clear [<target>]', required_superuser=True)
    async def _(msg: Bot.MessageSession):
        if '<target>' in msg.parsed_msg:
            group = msg.parsed_msg['<target>']
            target = BotDBUtil.TargetInfo(group)
            target.clear_petal()
            await msg.finish(msg.locale.t('core.message.petal.clear', target=group))
        else:
            msg.data.clear_petal()
            await msg.finish(msg.locale.t('core.message.petal.clear.self'))
            

if Bot.client_name == 'QQ':
    post_whitelist = module('post_whitelist', required_superuser=True, base=True)

    @post_whitelist.command('<group_id>')
    async def _(msg: Bot.MessageSession):
        target_data = BotDBUtil.TargetInfo(msg.parsed_msg['<group_id>'])
        k = 'in_post_whitelist'
        v = not target_data.options.get(k, False)
        target_data.edit_option(k, v)
        await msg.finish(msg.locale.t("core.message.set.help.option.success", k=k, v=v))

    lagrange = module('lagrange', required_superuser=True, base=True)

    @lagrange.command()
    async def _(msg: Bot.MessageSession):
        await msg.finish(f'Keepalive: {str(Temp.data.get("lagrange_keepalive", "None"))}\n'
                         f'Status: {str(Temp.data.get("lagrange_status", "None"))}\n'
                         f'Groups: {str(Temp.data.get("lagrange_available_groups", "None"))}')
