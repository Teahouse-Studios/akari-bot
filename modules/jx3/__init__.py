from core.component import on_command
from core.elements import MessageSession
from .jx3 import *

jx3 = on_command('jx3', developers=['HornCopper'])
                
@jx3.handle("status <server_name> {获取剑网三服务器状态}")
async def _(msg: MessageSession):
    server = msg.parsed_msg['<server_name>']
    msg.sendMessage(server_status(server))
                 
@jx3.handle("horse <horse_name> {获取剑网三马匹刷新位置}")
async def _(msg: MessageSession):
    horse = nsg.parsed_msg['<horse_name>']
    msg.sendMessage(horse_flush_place(horse))
