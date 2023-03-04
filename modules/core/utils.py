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
                     desc='查看机器人的版本号',
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
                  desc='获取机器人状态',
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
            GroupList = '无法获取'
        try:
            FriendList = len(await app.friendList())
        except Exception:
            FriendList = '无法获取'
        """
        BFH = r'%'
        result += (f"\n系统运行时间：{Boot_Start}"
                   + f"\n机器人已运行：{timediff}"
                   + f"\nPython版本：{platform.python_version()}"
                   + f"\n处理器型号：{get_cpu_info()['brand_raw']}"
                   + f"\n当前处理器使用率：{Cpu_usage}{BFH}"
                   + f"\n物理内存：{RAM}M 使用率：{RAM_percent}{BFH}"
                   + f"\nSwap内存：{Swap}M 使用率：{Swap_percent}{BFH}"
                   + f"\n磁盘容量：{Disk}G/{DiskTotal}G"
                   # + f"\n已加入QQ群聊：{GroupList}"
                   # + f" | 已添加QQ好友：{FriendList}" """
                   )
    await msg.finish(result)


admin = module('admin',
                   base=True,
                   required_admin=True,
                   developers=['OasisAkari'],
                   desc='一些群聊管理员可使用的命令。'
                   )


@admin.handle([
                  'add <UserID> {设置成员为机器人管理员，实现不设置成员为群聊管理员的情况下管理机器人的功能。已是群聊管理员无需设置此项目。}',
                  'del <UserID> {取消成员的机器人管理员}',
                  'list {列出所有机器人管理员}'])
async def config_gu(msg: Bot.MessageSession):
    if 'list' in msg.parsed_msg:
        if msg.custom_admins:
            await msg.finish(f"当前机器人群内手动设置的管理员：\n" + '\n'.join(msg.custom_admins))
        else:
            await msg.finish("当前没有手动设置的机器人管理员。")
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误，请对象使用{msg.prefixes[0]}whoami命令查看用户ID。')
    if 'add' in msg.parsed_msg:
        if user and user not in msg.custom_admins:
            if msg.data.add_custom_admin(user):
                await msg.finish("成功")
        else:
            await msg.finish("此成员已经是机器人管理员。")
    if 'del' in msg.parsed_msg:
        if user:
            if msg.data.remove_custom_admin(user):
                await msg.finish("成功")


@admin.handle('ban <UserID> {限制某人在本群使用机器人}', 'unban <UserID> {解除对某人在本群使用机器人的限制}')
async def config_ban(msg: Bot.MessageSession):
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误，格式应为“{msg.target.senderFrom}|<用户ID>”')
    if user == msg.target.senderId:
        await msg.finish("你不可以对自己进行此操作！")
    if 'ban' in msg.parsed_msg:
        if user not in msg.options.get('ban', []):
            msg.data.edit_option('ban', msg.options.get('ban', []) + [user])
            await msg.finish("成功")
        else:
            await msg.finish("此成员已经被设置禁止使用机器人了。")
    if 'unban' in msg.parsed_msg:
        if user in (banlist := msg.options.get('ban', [])):
            banlist.remove(user)
            msg.data.edit_option('ban', banlist)
            await msg.finish("成功")
        else:
            await msg.finish("此成员没有被设置禁止使用机器人。")


locale = module('locale',
                    base=True,
                    required_admin=True,
                    developers=['Dianliang233'],
                    desc='用于设置机器人运行语言。'
                    )


@locale.handle(['<lang> {设置机器人运行语言}'])
async def config_gu(msg: Bot.MessageSession):
    lang = msg.parsed_msg['<lang>']
    if lang in ['zh_cn', 'zh_tw', 'en_us']:
        if BotDBUtil.TargetInfo(msg.target.targetId).edit('locale', lang):
            await msg.finish(msg.locale.t('success'))
    else:
        await msg.finish(f"语言格式错误，支持的语言有：{'、'.join(get_available_locales())}。")


whoami = module('whoami', developers=['Dianliang233'], base=True)


@whoami.handle('{获取发送命令的账号在机器人内部的 ID}')
async def _(msg: Bot.MessageSession):
    rights = ''
    if await msg.checkNativePermission():
        rights += '\n（你拥有本对话的管理员权限）'
    elif await msg.checkPermission():
        rights += '\n（你拥有本对话的机器人管理员权限）'
    if msg.checkSuperUser():
        rights += '\n（你拥有本机器人的超级用户权限）'
    await msg.finish(f'你的 ID 是：{msg.target.senderId}\n本对话的 ID 是：{msg.target.targetId}' + rights,
                     disable_secret_check=True)


tog = module('toggle', developers=['OasisAkari'], base=True, required_admin=True)


@tog.handle('typing {切换是否展示输入提示}')
async def _(msg: Bot.MessageSession):
    target = BotDBUtil.SenderInfo(msg.target.senderId)
    state = target.query.disable_typing
    if not state:
        target.edit('disable_typing', True)
        await msg.finish('成功关闭输入提示。')
    else:
        target.edit('disable_typing', False)
        await msg.finish('成功打开输入提示。')


@tog.handle('check {切换是否展示命令错字检查提示}')
async def _(msg: Bot.MessageSession):
    state = msg.options.get('typo_check')
    if state is None:
        state = False
    else:
        state = not state
    msg.data.edit_option('typo_check', state)
    await msg.finish(f'成功{"打开" if state else "关闭"}错字检查提示。')


mute = module('mute', developers=['Dianliang233'], base=True, required_admin=True,
                  desc='使机器人停止发言。')


@mute.handle()
async def _(msg: Bot.MessageSession):
    await msg.finish('成功禁言。' if msg.data.switch_mute() else '成功取消禁言。')


leave = module('leave', developers=['OasisAkari'], base=True, required_admin=True, available_for='QQ|Group',
                   desc='使机器人离开群聊。')


@leave.handle()
async def _(msg: Bot.MessageSession):
    confirm = await msg.waitConfirm('你确定吗？此操作不可逆。')
    if confirm:
        await msg.sendMessage('已执行。')
        await msg.call_api('set_group_leave', group_id=msg.session.target)
