import re

from .server import server
from .serverraw import serverraw


async def main(str1):
    if str1 == '-h':
        return ('''~server <address> - 从指定地址服务器的25565端口中获取Motd。
~server <address>:<port> - 从指定地址服务器的端口中获取Motd。
[-r] - 获取Motd的源代码。''')
    x = re.match(r'(?:.*\s?(-.*).*\s)|(?:.*(-.*))', str1)
    if x:
        if x.group(1) == '-r' or x.group(2) == '-r':
            str1 = re.sub(' -r|-r ', '', str1)
            return await serverraw(str1)
        else:
            return await server(str1)
    else:
        return await server(str1)


command = {'server': 'server'}
