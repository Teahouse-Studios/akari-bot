import asyncio
import time

import psutil
from graia.application import Group, Friend

from core.template import sendMessage, revokeMessage
from database import BotDB as database
from core.broadcast import app
from modules.utils.ab import ab
from modules.utils.newbie import newbie
from modules.utils.rc import rc


async def rc_loader(kwargs: dict):
    if Group in kwargs:
        table = 'start_wiki_link_group'
        id = kwargs[Group].id
    if Friend in kwargs:
        table = 'start_wiki_link_self'
        id = kwargs[Friend].id
    msg = await rc(table, id)
    await sendMessage(kwargs, msg)


async def ab_loader(kwargs: dict):
    if Group in kwargs:
        table = 'start_wiki_link_group'
        id = kwargs[Group].id
    if Friend in kwargs:
        table = 'start_wiki_link_self'
        id = kwargs[Friend].id
    msg = await ab(table, id)
    send = await sendMessage(kwargs, msg)


async def newbie_loader(kwargs: dict):
    if Group in kwargs:
        table = 'start_wiki_link_group'
        id = kwargs[Group].id
    if Friend in kwargs:
        table = 'start_wiki_link_self'
        id = kwargs[Friend].id
    msg = await newbie(table, id)
    await sendMessage(kwargs, msg)


async def ping(kwargs: dict):
    checkpermisson = database.check_superuser(kwargs)
    result = "Pong!"
    if checkpermisson:
        Boot_Start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
        time.sleep(0.5)
        Cpu_usage = psutil.cpu_percent()
        RAM = int(psutil.virtual_memory().total / (1024 * 1024))
        RAM_percent = psutil.virtual_memory().percent
        Swap = int(psutil.swap_memory().total / (1024 * 1024))
        Swap_percent = psutil.swap_memory().percent
        Disk = int(psutil.disk_usage('.').used / (1024 * 1024 * 1024))
        DiskTotal = int(psutil.disk_usage('.').total / (1024 * 1024 * 1024))
        try:
            GroupList = len(await app.groupList())
        except Exception:
            GroupList = '无法获取'
        try:
            FriendList = len(await app.friendList())
        except Exception:
            FriendList = '无法获取'
        BFH = r'%'
        result += (f"\n系统运行时间：{Boot_Start}"
                  + f"\n当前CPU使用率：{Cpu_usage}{BFH}"
                  + f"\n物理内存：{RAM}M 使用率：{RAM_percent}{BFH}"
                  + f"\nSwap内存：{Swap}M 使用率：{Swap_percent}{BFH}"
                  + f"\n磁盘容量：{Disk}G/{DiskTotal}G"
                  + f"\n已加入群聊：{GroupList}"
                  + f" | 已添加好友：{FriendList}")
    await sendMessage(kwargs, result)


command = {'rc': rc_loader, 'ab': ab_loader, 'newbie': newbie_loader}
essential = {'ping': ping}
help = {'rc': {'help': '~rc - 查询Wiki最近更改。'},
        'ab': {'help': '~ab - 查询Wiki滥用过滤器日志。'},
        'newbie': {'help': '~newbie - 查询Wiki用户注册日志。'},
        'ping': {'help': '~ping - PongPongPong', 'essential': True}}
