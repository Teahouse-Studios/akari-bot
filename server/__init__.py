import re
from .server import server
from .serverraw import serverraw
async def ser(str1):
    str1 = re.sub(r'^Server','server',str1)
    print (str1)
    if str1.find(" -h") != -1:
        return('''~server <address> - 从指定地址服务器的25565端口中获取Motd。
~server <address>:<port> - 从指定地址服务器的端口中获取Motd。
[-r] - 获取Motd的源代码。''')
    if str1.find(" -r") != -1:
        str1 = re.sub(' -r','',str1)
        str1 = re.match(r'^server (.*)',str1)
        return (serverraw(str1.group(1)))
    else:
        str1 = re.match(r'^server (.*)',str1)
        return (server(str1.group(1)))