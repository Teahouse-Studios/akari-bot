import os

from core.elements import MessageSession, Plain, Image
from core.component import on_command
from .getb30 import getb30
from .initialize import arcb30init


b30 = on_command('b30', developers=['OasisAkari'])


@b30.handle('<friendcode> {查询一个Arcaea用户的b30列表}')
async def main(msg: MessageSession):
    assets = os.path.abspath('assets/arcaea')
    friendcode = msg.parsed_msg['<friendcode>']
    if friendcode:
        if friendcode == 'initialize':
            if msg.checkSuperUser():
                return await arcb30init(msg)
            else:
                return await msg.sendMessage('权限不足')
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
