import re

from .server import server
from .serverraw import serverraw


async def main(message):
    if message == '-h':
        return ('''~server <address> - 从指定地址服务器的25565端口中获取Motd。
~server <address>:<port> - 从指定地址服务器的端口中获取Motd。
[-r] - 获取Motd的源代码。''')
    msgsplit = message.split(' ')
    if '-r' in msgsplit:
        message = re.sub(' -r|-r ', '', message)
        return await serverraw(message)
    else:
        return await server(message)


command = {'server': 'server'}
