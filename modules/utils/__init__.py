import asyncio
import time

import psutil
from graia.application import Group, Friend

from core.template import sendMessage, revokeMessage
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
    await asyncio.sleep(60)
    await revokeMessage(send)


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
    Boot_Start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
    time.sleep(0.5)
    Cpu_usage = psutil.cpu_percent()
    RAM = int(psutil.virtual_memory().total / (1027 * 1024))
    RAM_percent = psutil.virtual_memory().percent
    Swap = int(psutil.swap_memory().total / (1027 * 1024))
    Swap_percent = psutil.swap_memory().percent
    BFH = r'%'
    result = ("Pong!\n" + "系统运行时间：%s" % Boot_Start \
              + "\n当前CPU使用率：%s%s" % (Cpu_usage, BFH) \
              + "\n物理内存：%dM 使用率：%s%s" % (RAM, RAM_percent, BFH) \
              + "\nSwap内存：%dM 使用率：%s%s" % (Swap, Swap_percent, BFH))
    await sendMessage(kwargs, result)


command = {'rc': rc_loader, 'ab': ab_loader, 'newbie': newbie_loader}
essential = {'ping': ping}
help = {'rc': {'module': '查询Wiki最近更改。', 'help': '~rc - 查询Wiki最近更改。'},
        'ab': {'module': '查询Wiki滥用过滤器日志。', 'help': '~ab - 查询Wiki滥用过滤器日志。'},
        'newbie': {'module': '查询Wiki用户注册日志。', 'help': '~newbie - 查询Wiki用户注册日志。'},
        'ping': {'module': 'Pong', 'help': '~ping - PongPongPong', 'essential': True}}
