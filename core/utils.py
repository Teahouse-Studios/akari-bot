import os
import re

import aiohttp

from core.elements import Target
from core.template import sendMessage
from graia.application.message.chain import MessageChain
from graia.application.message.elements.internal import Image, Plain


async def load_prompt():
    authorcache = os.path.abspath('.cache_restart_author')
    loadercache = os.path.abspath('.cache_loader')
    if os.path.exists(authorcache):
        import json
        from core.template import sendMessage
        openauthorcache = open(authorcache, 'r')
        cachejson = json.loads(openauthorcache.read())
        openloadercache = open(loadercache, 'r')
        await sendMessage(cachejson, openloadercache.read(), Quote=False)
        openloadercache.close()
        openauthorcache.close()
        os.remove(authorcache)
        os.remove(loadercache)

async def get_url(url: str, headers=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20), headers=headers) as req:
            text = await req.text()
            return text


async def getsetu(kwargs):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(60)) as session:
        qqavatarbase = 'https://ptlogin2.qq.com/getface?appid=1006102&imgtype=3&uin=' + str(kwargs[Target].senderId)
        async with session.get(qqavatarbase) as qlink:
            try:
                qqavatarlink = re.match(r'pt.setHeader\({".*?":"(https://thirdqq.qlogo.cn/.*)"}\)',
                                        await qlink.text())
                qqavatarlink = qqavatarlink.group(1)
            except Exception:
                qqavatarlink = False
    if qqavatarlink:
        await sendMessage(kwargs, MessageChain.create([Plain(f'↓╰♡╮極мī鏈接，速嚸╭♡╯↓\n{qqavatarlink}')]))
        await sendMessage(kwargs, MessageChain.create([Image.fromNetworkAddress(qqavatarlink)]), Quote=False)
