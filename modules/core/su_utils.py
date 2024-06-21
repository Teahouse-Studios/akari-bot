import os
import re
import shutil
import sys
from datetime import datetime

import ujson as json

from config import Config, CFG
from core.builtins import Bot, PrivateAssets, Plain, ExecutionLockList, Temp, MessageTaskManager
from core.component import module
from core.exceptions import NoReportException, TestException
from core.loader import ModulesManager
from core.logger import Logger
from core.parser.message import check_temp_ban, remove_temp_ban
from core.tos import pardon_user, warn_user
from core.utils.info import Info
from core.utils.storedata import get_stored_list, update_stored_list
from database import BotDBUtil


target_list = ["Discord|Channel", "Discord|DM|Channel", "KOOK|Group",
               "Matrix|Room", "QQ|Group", "QQ|Guild", "QQ|Private", "Telegram|Channel",
               "Telegram|Group", "Telegram|Private", "Telegram|Supergroup",]
sender_list = ["Discord|Client", "KOOK|User", "Matrix", "QQ", "QQ|Tiny", "Telegram|User",]


su = module('superuser', alias='su', required_superuser=True, base=True)


@su.command('add <user>')
async def add_su(msg: Bot.MessageSession, user: str):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', True):
            await msg.finish(msg.locale.t("success"))


@su.command('remove <user>')
async def del_su(msg: Bot.MessageSession, user: str):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    if user == msg.target.sender_id:
        confirm = await msg.wait_confirm(msg.locale.t("core.message.admin.remove.confirm"), append_instruction=False)
        if not confirm:
            await msg.finish()
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', False):
            await msg.finish(msg.locale.t("success"))


purge = module('purge', required_superuser=True, base=True)


@purge.command()
async def _(msg: Bot.MessageSession):
    cache_path = os.path.abspath(Config('cache_path', './cache/'))
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


@set_.command('module enable <target> <modules> ...',
              'module disable <target> <modules> ...',
              'module list <target>')
async def _(msg: Bot.MessageSession, target: str):
    if not any(target.startswith(f'{target_from}|') for target_from in target_list):
        await msg.finish(msg.locale.t("message.id.invalid.target", target=msg.target.target_from))
    target_data = BotDBUtil.TargetInfo(target)
    if not target_data.query:
        confirm = await msg.wait_confirm(msg.locale.t("core.message.set.confirm.init"), append_instruction=False)
        if not confirm:
            await msg.finish()
    if 'enable' in msg.parsed_msg:
        modules = [m for m in [msg.parsed_msg['<modules>']] + msg.parsed_msg.get('...', [])
                   if m in ModulesManager.return_modules_list(msg.target.target_from)]
        target_data.enable(modules)
        if modules:
            await msg.finish(msg.locale.t("core.message.set.module.enable.success") + ", ".join(modules))
        else:
            await msg.finish(msg.locale.t("core.message.set.module.enable.failed"))
    elif 'disable' in msg.parsed_msg:
        modules = [m for m in [msg.parsed_msg['<modules>']] + msg.parsed_msg.get('...', [])
                   if m in target_data.enabled_modules]
        target_data.disable(modules)
        if modules:
            await msg.finish(msg.locale.t("core.message.set.module.disable.success") + ", ".join(modules))
        else:
            await msg.finish(msg.locale.t("core.message.set.module.disable.failed"))
    elif 'list' in msg.parsed_msg:
        modules = sorted(target_data.enabled_modules)
        if modules:
            await msg.finish([Plain(msg.locale.t("core.message.set.module.list")), Plain(" | ".join(modules))])
        else:
            await msg.finish(msg.locale.t("core.message.set.module.list.none"))


@set_.command('option get <target> [<k>]',
              'option edit <target> <k> <v>',
              'option remove <target> <k>')
async def _(msg: Bot.MessageSession, target: str):
    if not any(target.startswith(f'{target_from}|') for target_from in target_list):
        await msg.finish(msg.locale.t("message.id.invalid.target", target=msg.target.target_from))
    target_data = BotDBUtil.TargetInfo(target)
    if not target_data.query:
        confirm = await msg.wait_confirm(msg.locale.t("core.message.set.confirm.init"), append_instruction=False)
        if not confirm:
            await msg.finish()
    if 'get' in msg.parsed_msg:
        k = msg.parsed_msg.get('<k>', None)
        await msg.finish(str(target_data.get_option(k)))
    elif 'edit' in msg.parsed_msg:
        k = msg.parsed_msg.get('<k>')
        v = msg.parsed_msg.get('<v>')
        if v.startswith(('[', '{')):
            v = json.loads(v)
        elif v.upper() == 'TRUE':
            v = True
        elif v.upper() == 'FALSE':
            v = False
        target_data.edit_option(k, v)
        await msg.finish(msg.locale.t("core.message.set.option.edit.success", k=k, v=v))
    elif 'remove' in msg.parsed_msg:
        k = msg.parsed_msg.get('<k>')
        target_data.remove_option(k)
        await msg.finish(msg.locale.t("success"))


if Bot.client_name == 'QQ':
    post_whitelist = module('post_whitelist', required_superuser=True, base=True)

    @post_whitelist.command('<group_id>')
    async def _(msg: Bot.MessageSession, group_id: str):
        if not group_id.startswith('QQ|Group|'):
            await msg.finish(msg.locale.t("message.id.invalid.target", target='QQ|Group'))
        target_data = BotDBUtil.TargetInfo(group_id)
        k = 'in_post_whitelist'
        v = not target_data.options.get(k, False)
        target_data.edit_option(k, v)
        await msg.finish(msg.locale.t("core.message.set.option.edit.success", k=k, v=v))


ae = module('abuse', alias='ae', required_superuser=True, base=True)


@ae.command('check <user>')
async def _(msg: Bot.MessageSession, user: str):
    stat = ''
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    warns = BotDBUtil.SenderInfo(user).query.warns
    temp_banned_time = await check_temp_ban(user)
    is_banned = BotDBUtil.SenderInfo(user).query.isInBlockList
    if temp_banned_time:
        stat += '\n' + msg.locale.t("core.message.abuse.check.tempbanned", ban_time=temp_banned_time)
    if is_banned:
        stat += '\n' + msg.locale.t("core.message.abuse.check.banned")
    await msg.finish(msg.locale.t("core.message.abuse.check.warns", user=user, warns=warns) + stat)


@ae.command('warn <user> [<count>]')
async def _(msg: Bot.MessageSession, user: str, count: int = 1):
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    warn_count = await warn_user(user, count)
    await msg.finish(msg.locale.t("core.message.abuse.warn.success", user=user, count=count, warn_count=warn_count))


@ae.command('revoke <user> [<count>]')
async def _(msg: Bot.MessageSession, user: str, count: int = 1):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    warn_count = await warn_user(user, -count)
    await msg.finish(msg.locale.t("core.message.abuse.revoke.success", user=user, count=count, warn_count=warn_count))


@ae.command('clear <user>')
async def _(msg: Bot.MessageSession, user: str):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    await pardon_user(user)
    await msg.finish(msg.locale.t("core.message.abuse.clear.success", user=user))


@ae.command('untempban <user>')
async def _(msg: Bot.MessageSession, user: str):
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    await remove_temp_ban(user)
    await msg.finish(msg.locale.t("core.message.abuse.untempban.success", user=user))


@ae.command('ban <user>')
async def _(msg: Bot.MessageSession, user: str):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', True):
        await msg.finish(msg.locale.t("core.message.abuse.ban.success", user=user))


@ae.command('unban <user>')
async def _(msg: Bot.MessageSession, user: str):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', False):
        await msg.finish(msg.locale.t("core.message.abuse.unban.success", user=user))


if Bot.client_name == 'QQ':
    @ae.command('block <target>')
    async def _(msg: Bot.MessageSession, target: str):
        if not target.startswith('QQ|Group|'):
            await msg.finish(msg.locale.t("message.id.invalid.target", target='QQ|Group'))
        if target == msg.target.target_id:
            await msg.finish(msg.locale.t("core.message.abuse.block.self"))
        if BotDBUtil.GroupBlockList.add(target):
            await msg.finish(msg.locale.t("core.message.abuse.block.success", target=target))

    @ae.command('unblock <target>')
    async def _(msg: Bot.MessageSession, target: str):
        if not target.startswith('QQ|Group|'):
            await msg.finish(msg.locale.t("message.id.invalid.target", target='QQ|Group'))
        if BotDBUtil.GroupBlockList.remove(target):
            await msg.finish(msg.locale.t("core.message.abuse.unblock.success", target=target))


res = module('reset', required_superuser=True, base=True)


@res.command()
async def reset(msg: Bot.MessageSession):
    confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False)
    if confirm:
        pull_repo_result = os.popen('git reset --hard origin/master', 'r').read()[:-1]
        if pull_repo_result != '':
            await msg.finish(pull_repo_result)
        else:
            await msg.finish(msg.locale.t("core.message.update.failed"))
    else:
        await msg.finish()


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
    pull_repo_result = pull_repo()
    if pull_repo_result:
        await msg.send_message(pull_repo_result)
    else:
        await msg.send_message(msg.locale.t("core.message.update.failed"))
    await msg.finish(update_dependencies())


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
                await msg.sleep(10)
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


exit_ = module('exit', required_superuser=True, base=True, available_for=['TEST|Console'])


@exit_.command()
async def _(msg: Bot.MessageSession):
    confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False, delete=False)
    if confirm:
        await msg.sleep(0.5)
        sys.exit()


if Bot.FetchTarget.name == 'QQ':
    resume = module('resume', required_base_superuser=True, base=True)

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
                await msg.sleep(30)
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
                await msg.sleep(30)
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
async def _(msg: Bot.MessageSession, display_msg: str):
    await msg.finish(display_msg)


say = module('say', required_superuser=True, base=True)


@say.command('<display_msg>')
async def _(msg: Bot.MessageSession, display_msg: str):
    await msg.finish(display_msg, quote=False)


rse = module('raise', required_superuser=True, base=True)


@rse.command()
async def _(msg: Bot.MessageSession):
    e = msg.locale.t("core.message.raise")
    raise TestException(e)


if Config('enable_eval', False):
    _eval = module('eval', required_superuser=True, base=True)

    @_eval.command('<display_msg>')
    async def _(msg: Bot.MessageSession, display_msg: str):
        try:
            await msg.finish(str(eval(display_msg, {'msg': msg})))
        except Exception as e:
            raise NoReportException(e)


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


@cfg_.command('get <k>')
async def _(msg: Bot.MessageSession, k: str):
    await msg.finish(str(Config(k)))


@cfg_.command('write <k> <v> [-s]')
async def _(msg: Bot.MessageSession, k: str, v: str):
    if v.lower() == 'true':
        v = True
    elif v.lower() == 'false':
        v = False
    elif isint(v):
        v = int(v)
    elif isfloat(v):
        v = float(v)
    elif re.match(r'^\[.*\]$', v):
        try:
            v = json.loads(v)
        except BaseException:
            await msg.finish(msg.locale.t("core.message.config.write.failed"))

    CFG.write(k, v, msg.parsed_msg['-s'])
    await msg.finish(msg.locale.t("success"))


@cfg_.command('delete <k>')
async def _(msg: Bot.MessageSession, k: str):
    if CFG.delete(k):
        await msg.finish(msg.locale.t("success"))
    else:
        await msg.finish(msg.locale.t("failed"))


if Config('enable_petal', False):
    petal = module('petal', base=True, alias='petals')

    @petal.command()
    async def _(msg: Bot.MessageSession):
        await msg.finish(msg.locale.t('core.message.petal.self', petal=msg.data.petal))

    @petal.command('[<target>] {{core.help.petal}}', required_superuser=True)
    async def _(msg: Bot.MessageSession):
        target = msg.parsed_msg['<target>']
        if not any(target.startswith(f'{target_from}|') for target_from in target_list):
            await msg.finish(msg.locale.t("message.id.invalid.target", target=msg.target.target_from))
        target_info = BotDBUtil.TargetInfo(target)
        await msg.finish(msg.locale.t('core.message.petal', target=target, petal=target_info.petal))

    @petal.command('modify <petal> [<target>]', required_superuser=True)
    async def _(msg: Bot.MessageSession, petal: str):
        if '<target>' in msg.parsed_msg:
            target = msg.parsed_msg['<target>']
            if not any(target.startswith(f'{target_from}|') for target_from in target_list):
                await msg.finish(msg.locale.t("message.id.invalid.target", target=msg.target.target_from))
            target_info = BotDBUtil.TargetInfo(target)
            target_info.modify_petal(int(petal))
            await msg.finish(
                msg.locale.t('core.message.petal.modify', target=target, add_petal=petal, petal=target_info.petal))
        else:
            msg.data.modify_petal(int(petal))
            await msg.finish(msg.locale.t('core.message.petal.modify.self', add_petal=petal, petal=msg.data.petal))

    @petal.command('clear [<target>]', required_superuser=True)
    async def _(msg: Bot.MessageSession):
        if '<target>' in msg.parsed_msg:
            target = msg.parsed_msg['<target>']
            if not any(target.startswith(f'{target_from}|') for target_from in target_list):
                await msg.finish(msg.locale.t("message.id.invalid.target", target=msg.target.target_from))
            target_info = BotDBUtil.TargetInfo(target)
            target_info.clear_petal()
            await msg.finish(msg.locale.t('core.message.petal.clear', target=target))
        else:
            msg.data.clear_petal()
            await msg.finish(msg.locale.t('core.message.petal.clear.self'))

lagrange = module('lagrange', required_superuser=True, base=True)


@lagrange.command()
async def _(msg: Bot.MessageSession):
    await msg.finish(f'Keepalive: {str(Temp.data.get("lagrange_keepalive", "None"))}\n'
                     f'Status: {str(Temp.data.get("lagrange_status", "None"))}\n'
                     f'Groups: {str(Temp.data.get("lagrange_available_groups", "None"))}')
