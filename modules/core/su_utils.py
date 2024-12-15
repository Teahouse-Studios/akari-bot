import os
import re
import shutil
import sys
from datetime import datetime

import orjson as json

from core.builtins import Bot, I18NContext, PrivateAssets, Plain, ExecutionLockList, Temp, MessageTaskManager
from core.component import module
from core.config import Config, CFGManager
from core.constants.exceptions import NoReportException, TestException
from core.constants.path import cache_path
from core.database import BotDBUtil
from core.loader import ModulesManager
from core.logger import Logger
from core.parser.message import check_temp_ban, remove_temp_ban
from core.tos import pardon_user, warn_user
from core.types import Param
from core.utils.decrypt import decrypt_string
from core.utils.i18n import Locale
from core.utils.info import Info, get_all_sender_prefix, get_all_target_prefix
from core.utils.storedata import get_stored_list, update_stored_list
from core.utils.text import isfloat, isint

target_list = get_all_target_prefix()
sender_list = get_all_sender_prefix()


su = module('superuser', alias='su', required_superuser=True, base=True, doc=True, exclude_from=['TEST|Console'])


@su.command('add <user>')
async def add_su(msg: Bot.MessageSession, user: str):
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', True):
            await msg.finish(msg.locale.t("message.success"))


@su.command('remove <user>')
async def del_su(msg: Bot.MessageSession, user: str):
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    if user == msg.target.sender_id:
        confirm = await msg.wait_confirm(msg.locale.t("core.message.admin.remove.confirm"), append_instruction=False)
        if not confirm:
            await msg.finish()
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', False):
            await msg.finish(msg.locale.t("message.success"))


purge = module('purge', required_superuser=True, base=True, doc=True)


@purge.command()
async def _(msg: Bot.MessageSession):
    if os.path.exists(cache_path):
        if os.listdir(cache_path):
            shutil.rmtree(cache_path)
            os.makedirs(cache_path, exist_ok=True)
            await msg.finish(msg.locale.t("core.message.purge.success"))
        else:
            await msg.finish(msg.locale.t("core.message.purge.empty"))
    else:
        os.makedirs(cache_path, exist_ok=True)
        await msg.finish(msg.locale.t("core.message.purge.empty"))


set_ = module('set', required_superuser=True, base=True, doc=True, exclude_from=['TEST|Console'])


@set_.command('module enable <target> <modules> ...',
              'module disable <target> <modules> ...',
              'module list <target>')
async def _(msg: Bot.MessageSession, target: str):
    if not target.startswith(f'{msg.target.target_from}|'):
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
            await msg.finish([I18NContext("core.message.set.module.list"), Plain(" | ".join(modules))])
        else:
            await msg.finish(msg.locale.t("core.message.set.module.list.none"))


@set_.command('option get <target> [<k>]',
              'option edit <target> <k> <v>',
              'option delete <target> <k>')
async def _(msg: Bot.MessageSession, target: str):
    if not target.startswith(f'{msg.target.target_from}|'):
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
        if re.match(r'\[.*\]|\{.*\}', v):
            try:
                v = v.replace("'", "\"")
                v = json.loads(v)
            except json.JSONDecodeError as e:
                Logger.error(str(e))
                await msg.finish(msg.locale.t("message.failed"))
        elif v.lower() == 'true':
            v = True
        elif v.lower() == 'false':
            v = False
        target_data.edit_option(k, v)
        await msg.finish(msg.locale.t("core.message.set.option.edit.success", k=k, v=v))
    elif 'delete' in msg.parsed_msg:
        k = msg.parsed_msg.get('<k>')
        target_data.remove_option(k)
        await msg.finish(msg.locale.t("message.success"))


if Bot.client_name == 'QQ':
    post_whitelist = module('post_whitelist', required_superuser=True, base=True, doc=True)

    @post_whitelist.command('<group_id>')
    async def _(msg: Bot.MessageSession, group_id: str):
        if not group_id.startswith('QQ|Group|'):
            await msg.finish(msg.locale.t("message.id.invalid.target", target='QQ|Group'))
        target_data = BotDBUtil.TargetInfo(group_id)
        k = 'in_post_whitelist'
        v = not target_data.options.get(k, False)
        target_data.edit_option(k, v)
        await msg.finish(msg.locale.t("core.message.set.option.edit.success", k=k, v=v))


ae = module('abuse', alias='ae', required_superuser=True, base=True, doc=True, exclude_from=['TEST|Console'])


@ae.command('check <user>')
async def _(msg: Bot.MessageSession, user: str):
    stat = ''
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    sender_info = BotDBUtil.SenderInfo(user)
    warns = sender_info.warns
    temp_banned_time = await check_temp_ban(user)
    if temp_banned_time:
        stat += '\n' + msg.locale.t("core.message.abuse.check.tempbanned", ban_time=temp_banned_time)
    if sender_info.is_in_allow_list:
        stat += '\n' + msg.locale.t("core.message.abuse.check.trusted")
    elif sender_info.is_in_block_list:
        stat += '\n' + msg.locale.t("core.message.abuse.check.banned")
    await msg.finish(msg.locale.t("core.message.abuse.check.warns", user=user, warns=warns) + stat)


@ae.command('warn <user> [<count>]')
async def _(msg: Bot.MessageSession, user: str, count: int = 1):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    warn_count = await warn_user(user, count)
    await msg.finish(msg.locale.t("core.message.abuse.warn.success", user=user, count=count, warn_count=warn_count))


@ae.command('revoke <user> [<count>]')
async def _(msg: Bot.MessageSession, user: str, count: int = 1):
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    warn_count = await warn_user(user, -count)
    await msg.finish(msg.locale.t("core.message.abuse.revoke.success", user=user, count=count, warn_count=warn_count))


@ae.command('clear <user>')
async def _(msg: Bot.MessageSession, user: str):
    if not user.startswith(f'{msg.target.sender_from}|'):
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
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    sender_info = BotDBUtil.SenderInfo(user)
    if sender_info.edit('isInBlockList', True) and sender_info.edit('isInAllowList', False):
        await msg.finish(msg.locale.t("core.message.abuse.ban.success", user=user))


@ae.command('unban <user>')
async def _(msg: Bot.MessageSession, user: str):
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    sender_info = BotDBUtil.SenderInfo(user)
    if sender_info.edit('isInBlockList', False):
        await msg.finish(msg.locale.t("core.message.abuse.unban.success", user=user))


@ae.command('trust <user>')
async def _(msg: Bot.MessageSession, user: str):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    sender_info = BotDBUtil.SenderInfo(user)
    if sender_info.edit('isInAllowList', True) and sender_info.edit('isInBlockList', False):
        await msg.finish(msg.locale.t("core.message.abuse.trust.success", user=user))


@ae.command('distrust <user>')
async def _(msg: Bot.MessageSession, user: str):
    if not any(user.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    sender_info = BotDBUtil.SenderInfo(user)
    if sender_info.edit('isInAllowList', False):
        await msg.finish(msg.locale.t("core.message.abuse.distrust.success", user=user))

    @ae.command('block <target>', load=(Bot.client_name == 'QQ'))
    async def _(msg: Bot.MessageSession, target: str):
        if not target.startswith('QQ|Group|'):
            await msg.finish(msg.locale.t("message.id.invalid.target", target='QQ|Group'))
        if target == msg.target.target_id:
            await msg.finish(msg.locale.t("core.message.abuse.block.self"))
        if BotDBUtil.GroupBlockList.add(target):
            await msg.finish(msg.locale.t("core.message.abuse.block.success", target=target))

    @ae.command('unblock <target>', load=(Bot.client_name == 'QQ'))
    async def _(msg: Bot.MessageSession, target: str):
        if not target.startswith('QQ|Group|'):
            await msg.finish(msg.locale.t("message.id.invalid.target", target='QQ|Group'))
        if BotDBUtil.GroupBlockList.remove(target):
            await msg.finish(msg.locale.t("core.message.abuse.unblock.success", target=target))


upd = module('update', required_superuser=True, base=True, doc=True)


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
    if not Info.binary_mode:
        if Info.version:
            pull_repo_result = pull_repo()
            if pull_repo_result:
                await msg.send_message(pull_repo_result)
            else:
                Logger.warning('Failed to get Git repository result.')
                await msg.send_message(msg.locale.t("core.message.update.failed"))
        await msg.finish(update_dependencies())
    else:
        await msg.finish(msg.locale.t("core.message.update.binary_mode"))

rst = module('restart', required_superuser=True, base=True, doc=True, load=Info.subprocess)


def restart():
    sys.exit(233)


def write_version_cache(msg: Bot.MessageSession):
    update = os.path.join(PrivateAssets.path, 'cache_restart_author')
    with open(update, 'wb') as write_version:
        write_version.write(json.dumps({'From': msg.target.target_from, 'ID': msg.target.target_id}))


restart_time = []


async def wait_for_restart(msg: Bot.MessageSession):
    get = ExecutionLockList.get()
    if datetime.now().timestamp() - restart_time[0] < 60:
        if len(get) != 0:
            await msg.send_message(msg.locale.t("core.message.restart.wait", count=len(get)))
            await msg.sleep(10)
            return await wait_for_restart(msg)
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

upds = module('update&restart', required_superuser=True, alias='u&r', base=True, doc=True, load=Info.subprocess)


@upds.command()
async def update_and_restart_bot(msg: Bot.MessageSession):
    if not Info.binary_mode:
        confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False)
        if confirm:
            restart_time.append(datetime.now().timestamp())
            await wait_for_restart(msg)
            write_version_cache(msg)
            if Info.version:
                pull_repo_result = pull_repo()
                if pull_repo_result != '':
                    await msg.send_message(pull_repo_result)
                else:
                    Logger.warning('Failed to get Git repository result.')
                    await msg.send_message(msg.locale.t("core.message.update.failed"))
            await msg.send_message(update_dependencies())
            restart()
        else:
            await msg.finish()
    else:
        await msg.finish(msg.locale.t("core.message.update.binary_mode"))


exit_ = module('exit', required_superuser=True, base=True, doc=True, available_for=['TEST|Console'])


@exit_.command()
async def _(msg: Bot.MessageSession):
    confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False, delete=False)
    if confirm:
        await msg.sleep(0.5)
        sys.exit()


resume = module('resume', required_base_superuser=True, base=True, doc=True, load=(Bot.FetchTarget.name == 'QQ'))


@resume.command()
async def _(msg: Bot.MessageSession):
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
async def _(msg: Bot.MessageSession):
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

forward_msg = module('forward_msg', required_superuser=True, base=True, doc=True, load=(Bot.FetchTarget.name == 'QQ'))


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


echo = module('echo', required_superuser=True, base=True, doc=True)


@echo.command('<display_msg>')
async def _(msg: Bot.MessageSession, dis: Param("<display_msg>", str)):
    await msg.finish(dis, enable_parse_message=False)


say = module('say', required_superuser=True, base=True, doc=True)


@say.command('<display_msg>')
async def _(msg: Bot.MessageSession, display_msg: str):
    await msg.finish(display_msg, quote=False)


rse = module('raise', required_superuser=True, base=True, doc=True)


@rse.command()
async def _(msg: Bot.MessageSession):
    e = msg.locale.t("core.message.raise")
    raise TestException(e)


_eval = module('eval', required_superuser=True, base=True, doc=True, load=Config('enable_eval', False))


@_eval.command('<display_msg>')
async def _(msg: Bot.MessageSession, display_msg: str):
    try:
        await msg.finish(str(eval(display_msg, {'msg': msg})))  # skipcq
    except Exception as e:
        Logger.error(str(e))
        raise NoReportException(e)


post_ = module('post', required_superuser=True, base=True, doc=True)


@post_.command('<target> <post_msg>')
async def _(msg: Bot.MessageSession, target: str, post_msg: str):
    if not target.startswith(f'{msg.target.client_name}|'):
        await msg.finish(msg.locale.t('message.id.invalid.target', target=msg.target.target_from))
    post_msg = f'{Locale(Config('default_locale', 'zh_cn')).t("core.message.post.prefix")} {post_msg}'
    session = await Bot.FetchTarget.fetch_target(target)
    confirm = await msg.wait_confirm(msg.locale.t("core.message.post.confirm", target=target, post_msg=post_msg), append_instruction=False)
    if confirm:
        await Bot.FetchTarget.post_global_message(post_msg, [session])
        await msg.finish(msg.locale.t("core.message.post.success"))
    else:
        await msg.finish()


@post_.command('global <post_msg>')
async def _(msg: Bot.MessageSession, post_msg: str):
    post_msg = f'{Locale(Config('default_locale', 'zh_cn')).t("core.message.post.prefix")} {post_msg}'
    confirm = await msg.wait_confirm(msg.locale.t("core.message.post.global.confirm", post_msg=post_msg), append_instruction=False)
    if confirm:
        await Bot.FetchTarget.post_global_message(post_msg)
        await msg.finish(msg.locale.t("core.message.post.success"))
    else:
        await msg.finish()


cfg_ = module('config', required_superuser=True, alias='cfg', base=True, doc=True)


@cfg_.command('get <k> [<table_name>]')
async def _(msg: Bot.MessageSession, k: str, table_name: str = None):
    await msg.finish(str(Config(k, table_name=table_name)))


@cfg_.command('write <k> <v> [<table_name>] [-s]')
async def _(msg: Bot.MessageSession, k: str, v: str, table_name: str = None):
    secret = bool(msg.parsed_msg['-s'])
    if v.lower() == 'true':
        v = True
    elif v.lower() == 'false':
        v = False
    elif isint(v):
        v = int(v)
    elif isfloat(v):
        v = float(v)
    elif re.match(r'\[.*\]', v):
        try:
            v = v.replace("'", "\"")
            v = json.loads(v)
        except json.JSONDecodeError as e:
            Logger.error(str(e))
            await msg.finish(msg.locale.t("message.failed"))
    if (not table_name and secret) or (table_name and table_name.lower() == 'secret'):
        table_name = 'config'
        secret = True
    CFGManager.write(k, v, secret=secret, table_name=table_name)
    await msg.finish(msg.locale.t("message.success"))


@cfg_.command('delete <k> [<table_name>]')
async def _(msg: Bot.MessageSession, k: str, table_name: str = None):
    if CFGManager.delete(k, table_name):
        await msg.finish(msg.locale.t("message.success"))
    else:
        await msg.finish(msg.locale.t("message.failed"))

petal_ = module('petal', alias='petals', base=True, doc=True, load=Config('enable_petal', False))


@petal_.command('{{core.help.petal}}')
async def _(msg: Bot.MessageSession):
    await msg.finish(msg.locale.t('core.message.petal.self', petal=msg.petal))


@petal_.command('[<sender>]', required_superuser=True, exclude_from=['TEST|Console'])
async def _(msg: Bot.MessageSession):
    sender = msg.parsed_msg['<sender>']
    if not any(sender.startswith(f'{sender_from}|') for sender_from in sender_list):
        await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
    sender_info = BotDBUtil.SenderInfo(sender)
    await msg.finish(msg.locale.t('core.message.petal', sender=sender, petal=sender_info.petal))


@petal_.command('modify <petal>', available_for=['TEST|Console'])
@petal_.command('modify <petal> [<sender>]', required_superuser=True, exclude_from=['TEST|Console'])
async def _(msg: Bot.MessageSession, petal: int, sender: str = None):
    if sender:
        if not any(sender.startswith(f'{sender_from}|') for sender_from in sender_list):
            await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
        sender_info = BotDBUtil.SenderInfo(sender)
        sender_info.modify_petal(petal)
        await msg.finish(
            msg.locale.t('core.message.petal.modify', sender=sender, add_petal=petal, petal=sender_info.petal))
    else:
        sender_info = BotDBUtil.SenderInfo(msg.target.sender_id)
        sender_info.modify_petal(petal)
        await msg.finish(msg.locale.t('core.message.petal.modify.self', add_petal=petal, petal=sender_info.petal))


@petal_.command('clear', required_superuser=True, available_for=['TEST|Console'])
@petal_.command('clear [<sender>]', required_superuser=True, exclude_from=['TEST|Console'])
async def _(msg: Bot.MessageSession, sender: str = None):
    if sender:
        if not any(sender.startswith(f'{sender_from}|') for sender_from in sender_list):
            await msg.finish(msg.locale.t("message.id.invalid.sender", sender=msg.target.sender_from))
        sender_info = BotDBUtil.SenderInfo(sender)
        sender_info.clear_petal()
        await msg.finish(msg.locale.t('core.message.petal.clear', sender=sender))
    else:
        msg.info.clear_petal()
        await msg.finish(msg.locale.t('core.message.petal.clear.self'))


jobqueue = module('jobqueue', required_superuser=True, base=True)


@jobqueue.command('clear')
async def _(msg: Bot.MessageSession):
    BotDBUtil.JobQueue.clear(0)
    await msg.finish(msg.locale.t("message.success"))


decry = module('decrypt', required_superuser=True, base=True, doc=True)


@decry.command('<display_msg>')
async def _(msg: Bot.MessageSession):
    dec = decrypt_string(msg.as_display().split(' ', 1)[1])
    if dec:
        await msg.finish(dec)
    else:
        await msg.finish(msg.locale.t("message.failed"))
