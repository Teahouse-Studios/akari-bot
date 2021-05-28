import os

from graia.application import MessageChain
from graia.application.message.elements.internal import Image, Plain

from core.template import sendMessage
from database import BotDB as database
from .getb30 import getb30
from .initialize import arcb30init


async def main(kwargs: dict):
    message = kwargs['trigger_msg']
    message = message.split(' ')
    assets = os.path.abspath('assets/arcaea')
    if len(message) > 1:
        if message[1] == 'initialize':
            if database.check_superuser(kwargs):
                await arcb30init(kwargs)
            else:
                await sendMessage(kwargs, '权限不足')
                return
        else:
            if not os.path.exists(assets):
                msg = {'text': '未找到资源文件！请放置一枚arcaea的apk到机器人的assets目录并重命名为arc.apk后，使用~b30 initialize初始化资源。'}
            else:
                msg = await getb30(message[1])
    else:
        msg = {'text': '请输入好友码！~b30 <friendcode>'}

    if 'file' in msg:
        imgchain = MessageChain.create([Image.fromLocalFile(msg['file'])])
    else:
        imgchain = False
    msgchain = MessageChain.create([Plain(msg['text'])])
    if imgchain:
        msgchain = msgchain.plusWith(imgchain)
    await sendMessage(kwargs, msgchain)


command = {'b30': main}
help = {'b30': {'module': '查询Arcaea B30结果。', 'help': '~b30 <usercode> - 查询Arcaea B30结果。'}}
