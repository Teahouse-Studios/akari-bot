import platform
import time
from datetime import datetime, timedelta, tzinfo

import jwt
import psutil
from cpuinfo import get_cpu_info

from config import Config
from core.builtins import Bot, command_prefix
from core.component import module
from core.utils.i18n import get_available_locales, Locale, load_locale_file
from core.utils.info import Info
from database import BotDBUtil

jwt_secret = Config('jwt_secret')

ver = module('version', base=True)


@ver.command('{{core.help.version}}')
async def bot_version(msg: Bot.MessageSession):
    if Info.version:
        await msg.finish(msg.locale.t('core.message.version', commit=Info.version[0:6]))
    else:
        await msg.finish(msg.locale.t('core.message.version.unknown'))


ping = module('ping', base=True)

started_time = datetime.now()


@ping.command('{{core.help.ping}}')
async def _(msg: Bot.MessageSession):
    checkpermisson = msg.check_super_user()
    result = "Pong!"
    if checkpermisson:
        timediff = str(datetime.now() - started_time)
        boot_start = msg.ts2strftime(psutil.boot_time())
        cpu_usage = psutil.cpu_percent()
        ram = int(psutil.virtual_memory().total / (1024 * 1024))
        ram_percent = psutil.virtual_memory().percent
        swap = int(psutil.swap_memory().total / (1024 * 1024))
        swap_percent = psutil.swap_memory().percent
        disk = int(psutil.disk_usage('/').used / (1024 * 1024 * 1024))
        disk_total = int(psutil.disk_usage('/').total / (1024 * 1024 * 1024))
        """
        try:
            GroupList = len(await app.groupList())
        except Exception:
            GroupList = msg.locale.t('core.message.ping.failed')
        try:
            FriendList = len(await app.friendList())
        except Exception:
            FriendList = msg.locale.t('core.message.ping.failed')
        """
        result += '\n' + msg.locale.t("core.message.ping.detail",
                                      system_boot_time=boot_start,
                                      bot_running_time=timediff,
                                      python_version=platform.python_version(),
                                      cpu_brand=get_cpu_info()['brand_raw'],
                                      cpu_usage=cpu_usage,
                                      ram=ram,
                                      ram_percent=ram_percent,
                                      swap=swap,
                                      swap_percent=swap_percent,
                                      disk_space=disk,
                                      disk_space_total=disk_total)
    await msg.finish(result)


admin = module('admin', base=True, required_admin=True, desc='{core.help.admin.desc}')


@admin.command([
    'add <UserID> {{core.help.admin.add}}',
    'remove <UserID> {{core.help.admin.remove}}',
    'list {{core.help.admin.list}}'])
async def config_gu(msg: Bot.MessageSession):
    if 'list' in msg.parsed_msg:
        if msg.custom_admins:
            await msg.finish(msg.locale.t("core.message.admin.list") + '\n'.join(msg.custom_admins))
        else:
            await msg.finish(msg.locale.t("core.message.admin.list.none"))
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t('core.message.admin.invalid', target=msg.target.sender_from, prefix=msg.prefixes[0]))
    if 'add' in msg.parsed_msg:
        if user and user not in msg.custom_admins:
            if msg.data.add_custom_admin(user):
                await msg.finish(msg.locale.t("core.message.admin.add.success", user=user))
        else:
            await msg.finish(msg.locale.t("core.message.admin.already"))
    if 'remove' in msg.parsed_msg:
        if user == msg.target.sender_id:
            confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"))
            if not confirm:
                return
        if user:
            if msg.data.remove_custom_admin(user):
                await msg.finish(msg.locale.t("core.message.admin.remove.success", user=user))


@admin.command('ban <UserID> {{core.help.admin.ban}}',
               'unban <UserID> {{core.help.admin.unban}}')
async def config_ban(msg: Bot.MessageSession):
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.sender_from}|'):
        await msg.finish(msg.locale.t('core.message.admin.invalid', prefix=msg.prefixes[0]))
    if user == msg.target.sender_id:
        await msg.finish(msg.locale.t("core.message.admin.ban.self"))
    if 'ban' in msg.parsed_msg:
        if user not in msg.options.get('ban', []):
            msg.data.edit_option('ban', msg.options.get('ban', []) + [user])
            await msg.finish(msg.locale.t('success'))
        else:
            await msg.finish(msg.locale.t("core.message.admin.ban.already"))
    if 'unban' in msg.parsed_msg:
        if user in (banlist := msg.options.get('ban', [])):
            banlist.remove(user)
            msg.data.edit_option('ban', banlist)
            await msg.finish(msg.locale.t('success'))
        else:
            await msg.finish(msg.locale.t("core.message.admin.ban.not_yet"))


locale = module('locale', base=True, desc='{core.help.locale.desc}')


@locale.command()
async def _(msg: Bot.MessageSession):
    avaliable_lang = msg.locale.t("message.delimiter").join(get_available_locales())
    await msg.finish(
        f"{msg.locale.t('core.message.locale')}{msg.locale.t('language')}\n{msg.locale.t('core.message.locale.set.prompt', langlist=avaliable_lang, prefix=msg.prefixes[0])}")


@locale.command('<lang> {{core.help.locale.set}}', required_admin=True)
async def config_gu(msg: Bot.MessageSession):
    lang = msg.parsed_msg['<lang>']
    if lang in get_available_locales() and BotDBUtil.TargetInfo(msg.target.target_id).edit('locale', lang):
        await msg.send_message(Locale(lang).t('success'))
    else:
        avaliable_lang = msg.locale.t("message.delimiter").join(get_available_locales())
        await msg.finish(msg.locale.t("core.message.locale.set.invalid", langlist=avaliable_lang))


@locale.command('reload', required_superuser=True)
async def reload_locale(msg: Bot.MessageSession):
    err = load_locale_file()
    if len(err) == 0:
        await msg.send_message(msg.locale.t("success"))
    else:
        await msg.send_message(msg.locale.t("core.message.locale.reload.failed", detail='\n'.join(err)))


whoami = module('whoami', base=True)


@whoami.command('{{core.help.whoami}}')
async def _(msg: Bot.MessageSession):
    perm = ''
    if await msg.check_native_permission():
        perm += '\n' + msg.locale.t("core.message.whoami.admin")
    elif await msg.check_permission():
        perm += '\n' + msg.locale.t("core.message.whoami.botadmin")
    if msg.check_super_user():
        perm += '\n' + msg.locale.t("core.message.whoami.superuser")
    await msg.finish(
        msg.locale.t('core.message.whoami', senderid=msg.target.sender_id, targetid=msg.target.target_id) + perm,
        disable_secret_check=True)


setup = module('setup', base=True, required_admin=True, desc='{core.help.setup.desc}')


@setup.command('typing {{core.help.setup.typing}}')
async def _(msg: Bot.MessageSession):
    target = BotDBUtil.SenderInfo(msg.target.sender_id)
    state = target.query.disable_typing
    if not state:
        target.edit('disable_typing', True)
        await msg.finish(msg.locale.t('core.message.setup.typing.disable'))
    else:
        target.edit('disable_typing', False)
        await msg.finish(msg.locale.t('core.message.setup.typing.enable'))


@setup.command('check {{core.help.setup.check}}')
async def _(msg: Bot.MessageSession):
    state = msg.options.get('typo_check')
    if state:
        msg.data.edit_option('typo_check', False)
        await msg.finish(msg.locale.t('core.message.setup.check.enable'))
    else:
        msg.data.edit_option('typo_check', True)
        await msg.finish(msg.locale.t('core.message.setup.check.disable'))


@setup.command('timeoffset <offset> {{core.help.setup.timeoffset}}')
async def _(msg: Bot.MessageSession, offset: str):
    try:
        tstr_split = [int(part) for part in offset.split(':')]
        hour = tstr_split[0]
        minute = tstr_split[1] if len(tstr_split) > 1 else 0
        if minute == 0:
            offset = f"{'+' if hour >= 0 else '-'}{abs(hour)}"
        else:
            symbol = offset[0] if offset.startswith(("+", "-")) else "+"
            offset = f"{symbol}{abs(hour)}:{abs(minute):02d}"
        if hour > 12 or minute >= 60:
            raise ValueError
    except ValueError:
        await msg.finish(msg.locale.t('core.message.setup.timeoffset.invalid'))
    msg.data.edit_option('timezone_offset', offset)
    await msg.finish(msg.locale.t('core.message.setup.timeoffset.success', offset=offset))


mute = module('mute', base=True, required_admin=True)


@mute.command('{{core.help.mute}}')
async def _(msg: Bot.MessageSession):
    state = msg.data.switch_mute()
    if state:
        await msg.finish(msg.locale.t('core.message.mute.enable'))
    else:
        await msg.finish(msg.locale.t('core.message.mute.disable'))


leave = module('leave', base=True, required_admin=True, available_for='QQ|Group', alias='dismiss')


@leave.command('{{core.help.leave}}')
async def _(msg: Bot.MessageSession):
    confirm = await msg.wait_confirm(msg.locale.t('core.message.confirm'))
    if confirm:
        await msg.send_message(msg.locale.t('core.message.leave.success'))
        await msg.call_api('set_group_leave', group_id=msg.session.target)


token = module('token', base=True)


@token.command('<code> {{core.help.token}}')
async def _(msg: Bot.MessageSession):
    await msg.finish(jwt.encode({
        'exp': datetime.utcnow() + timedelta(seconds=60 * 60 * 24 * 7),  # 7 days
        'iat': datetime.utcnow(),
        'senderId': msg.target.sender_id,
        'code': msg.parsed_msg['<code>']
    }, bytes(jwt_secret, 'utf-8'), algorithm='HS256'))
