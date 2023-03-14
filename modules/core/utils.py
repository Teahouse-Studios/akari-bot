import os
import platform
import time
from datetime import datetime

import psutil
from cpuinfo import get_cpu_info

from core.builtins import Bot, PrivateAssets
from core.component import module
from core.utils.i18n import get_available_locales
from database import BotDBUtil

version = module('version',
                 base=True,
                 desc='{core.version.help}',
                 developers=['OasisAkari', 'Dianliang233']
                 )


@version.handle()
async def bot_version(msg: Bot.MessageSession):
    ver = os.path.abspath(PrivateAssets.path + '/version')
    tag = os.path.abspath(PrivateAssets.path + '/version_tag')
    open_version = open(ver, 'r')
    open_tag = open(tag, 'r')
    msgs = f'当前运行的代码版本号为：{open_tag.read()}（{open_version.read()}）'
    open_version.close()
    await msg.finish(msgs, msgs)


ping = module('ping',
              base=True,
              desc='{core.ping.help}',
              developers=['OasisAkari']
              )

started_time = datetime.now()


@ping.handle()
async def _(msg: Bot.MessageSession):
    checkpermisson = msg.checkSuperUser()
    result = "Pong!"
    if checkpermisson:
        timediff = str(datetime.now() - started_time)
        Boot_Start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
        Cpu_usage = psutil.cpu_percent()
        RAM = int(psutil.virtual_memory().total / (1024 * 1024))
        RAM_percent = psutil.virtual_memory().percent
        Swap = int(psutil.swap_memory().total / (1024 * 1024))
        Swap_percent = psutil.swap_memory().percent
        Disk = int(psutil.disk_usage('/').used / (1024 * 1024 * 1024))
        DiskTotal = int(psutil.disk_usage('/').total / (1024 * 1024 * 1024))
        """
        try:
            GroupList = len(await app.groupList())
        except Exception:
            GroupList = msg.locale.t('core.ping.message.failed')
        try:
            FriendList = len(await app.friendList())
        except Exception:
            FriendList = msg.locale.t('core.ping.message.failed')
        """
        result += '\n' + msg.locale.t("core.ping.message.detail", system_boot_time=Boot_Start, bot_running_time=timediff, python_version=platform.python_version(), cpu_brand=get_cpu_info()['brand_raw'], cpu_usage=Cpu_usage, ram=RAM, ram_percent=RAM_percent, swap=Swap, swap_percent=Swap_percent, disk_space=Disk, disk_space_total=DiskTotal)
    await msg.finish(result)


admin = module('admin',
               base=True,
               required_admin=True,
               developers=['OasisAkari'],
               desc='{core.admin.help}'
               )


@admin.handle([
    'add <UserID> {{core.admin.help.add}}',
    'del <UserID> {{core.admin.help.del}}',
    'list {{core.admin.help.list}}'])
async def config_gu(msg: Bot.MessageSession):
    if 'list' in msg.parsed_msg:
        if msg.custom_admins:
            await msg.finish(msg.locale.t("core.admin.message.list") + '\n'.join(msg.custom_admins))
        else:
            await msg.finish(msg.locale.t("core.admin.message.list.none"))
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(msg.locale.t('core.superuser.message.invalid', prefix=msg.prefixes[0]))
    if 'add' in msg.parsed_msg:
        if user and user not in msg.custom_admins:
            if msg.data.add_custom_admin(user):
                await msg.finish(msg.locale.t('success'))
        else:
            await msg.finish(msg.locale.t("core.admin.message.already"))
    if 'del' in msg.parsed_msg:
        if user:
            if msg.data.remove_custom_admin(user):
                await msg.finish(msg.locale.t('success'))


@admin.handle('ban <UserID> {{core.ban.help.ban}}', 'unban <UserID> {{core.ban.help.unban}}')
async def config_ban(msg: Bot.MessageSession):
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(msg.locale.t('core.ban.message.invalid' ,target=msg.target.senderFrom))
    if user == msg.target.senderId:
        await msg.finish(msg.locale.t("core.ban.message.self"))
    if 'ban' in msg.parsed_msg:
        if user not in msg.options.get('ban', []):
            msg.data.edit_option('ban', msg.options.get('ban', []) + [user])
            await msg.finish(msg.locale.t('success'))
        else:
            await msg.finish(msg.locale.t("core.ban.message.already"))
    if 'unban' in msg.parsed_msg:
        if user in (banlist := msg.options.get('ban', [])):
            banlist.remove(user)
            msg.data.edit_option('ban', banlist)
            await msg.finish(msg.locale.t('success'))
        else:
            await msg.finish(msg.locale.t("core.ban.message.not_yet"))


locale = module('locale',
                base=True,
                required_admin=True,
                developers=['Dianliang233'],
                desc='{core.locale.help}'
                )


@locale.handle(['<lang> {{core.locale.help.locale}}'])
async def config_gu(msg: Bot.MessageSession):
    lang = msg.parsed_msg['<lang>']
    if lang in ['zh_cn', 'zh_tw', 'en_us']:
        if BotDBUtil.TargetInfo(msg.target.targetId).edit('locale', lang):
            await msg.finish(msg.locale.t('success'))
    else:
        await msg.finish(msg.locale.t("core.locale.message.invalid",lang='、'.join(get_available_locales())))


whoami = module('whoami', developers=['Dianliang233'], base=True)


@whoami.handle('{{core.whoami.help}}')
async def _(msg: Bot.MessageSession):
    rights = ''
    if await msg.checkNativePermission():
        rights += '\n' + msg.locale.t("core.whoami.message.admin")
    elif await msg.checkPermission():
        rights += '\n' + msg.locale.t("core.whoami.message.botadmin")
    if msg.checkSuperUser():
        rights += '\n' + msg.locale.t("core.whoami.message.superuser")
    await msg.finish(msg.locale.t('core.whoami.message', senderid=msg.target.senderId, targetid=msg.target.targetId) + rights,
                     disable_secret_check=True)


tog = module('toggle', developers=['OasisAkari'], base=True, required_admin=True)


@tog.handle('typing {{core.toggle.help.typing}}')
async def _(msg: Bot.MessageSession):
    target = BotDBUtil.SenderInfo(msg.target.senderId)
    state = target.query.disable_typing
    if not state:
        target.edit('disable_typing', True)
        await msg.finish(msg.locale.t('core.toggle.message.typing.disable'))
    else:
        target.edit('disable_typing', False)
        await msg.finish(msg.locale.t('core.toggle.message.typing.enable'))


@tog.handle('check {{core.toggle.help.check}}')
async def _(msg: Bot.MessageSession):
    state = msg.options.get('typo_check')
    if state is None:
        state = False
    else:
        state = not state
    msg.data.edit_option('typo_check', state)
    await msg.finish(msg.locale.t('core.toggle.message.check.enable') if state else msg.locale.t('core.toggle.message.check.disable'))


mute = module('mute', developers=['Dianliang233'], base=True, required_admin=True,
              desc='{core.mute.help}')


@mute.handle()
async def _(msg: Bot.MessageSession):
    await msg.finish(msg.locale.t('core.mute.message.enable') if msg.data.switch_mute() else msg.locale.t('core.mute.message.disable'))


leave = module('leave', developers=['OasisAkari'], base=True, required_admin=True, available_for='QQ|Group', alias={'dismiss': 'leave'},
               desc='{core.leave.help}')


@leave.handle()
async def _(msg: Bot.MessageSession):
    confirm = await msg.waitConfirm(msg.locale.t('core.leave.confirm'))
    if confirm:
        await msg.sendMessage(msg.locale.t('core.leave.message'))
        await msg.call_api('set_group_leave', group_id=msg.session.target)
