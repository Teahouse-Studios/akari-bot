import os

from core.elements import MessageSession, Plain, Image
from core.loader.decorator import command
from .getb30 import getb30
from .initialize import arcb30init


@command('b30', help_doc='~b30 <friendcode>')
async def main(msg: MessageSession):
    assets = os.path.abspath('assets/arcaea')
    friendcode = msg.parsed_msg['<friendcode>']
    if friendcode:
        if friendcode == 'initialize':
            if msg.checkSuperuser():
                await arcb30init(msg)
            else:
                await msg.sendMessage('权限不足')
                return
        else:
            if not os.path.exists(assets):
                resp = {'text': '未找到资源文件！请放置一枚arcaea的apk到机器人的assets目录并重命名为arc.apk后，使用~b30 initialize初始化资源。'}
            else:
                resp = await getb30(friendcode)
    else:
        resp = {'text': '请输入好友码！'}
    msgchain = [Plain(resp['text'])]
    if 'file' in resp and msg.Feature.image:
        msgchain.append(Image(path=resp['file']))
    await msg.sendMessage(msgchain)