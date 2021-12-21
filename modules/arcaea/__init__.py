import os

from config import Config
from core.component import on_command
from core.elements import MessageSession, Plain, Image
from core.utils import get_url
from .getb30 import getb30
from .info import get_info
from .initialize import arcb30init

arc = on_command('arcaea', developers=['OasisAkari'], desc='查询Arcaea相关内容。',
                 alias={'b30': 'arcaea b30', 'a': 'arcaea', 'arc': 'arcaea'})


@arc.handle('b30 <friendcode> {查询一个Arcaea用户的b30列表}')
async def _(msg: MessageSession):
    assets = os.path.abspath('assets/arcaea')
    if not os.path.exists(assets):
        await msg.sendMessage('未找到资源文件！请放置一枚arcaea的apk到机器人的assets目录并重命名为arc.apk后，使用~arcaea initialize初始化资源。')
        return
    friendcode = msg.parsed_msg['<friendcode>']
    if friendcode:
        resp = await getb30(friendcode)
    else:
        resp = {'text': '请输入好友码！'}
    msgchain = [Plain(resp['text'])]
    if 'file' in resp and msg.Feature.image:
        msgchain.append(Image(path=resp['file']))
    await msg.sendMessage(msgchain)


@arc.handle('info <friendcode>  {查询一个Arcaea用户的最近游玩记录}')
async def _(msg: MessageSession):
    assets = os.path.abspath('assets/arcaea')
    if not os.path.exists(assets):
        await msg.sendMessage('未找到资源文件！请放置一枚arcaea的apk到机器人的assets目录并重命名为arc.apk后，使用~arcaea initialize初始化资源。')
        return
    friendcode = msg.parsed_msg['<friendcode>']
    resp = await get_info(friendcode)
    await msg.sendMessage(resp)


@arc.handle('initialize', required_superuser=True)
async def _(msg: MessageSession):
    return await arcb30init(msg)


@arc.handle('download {获取最新版本的游戏apk}')
async def _(msg: MessageSession):
    webrender = Config('web_render')
    resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/', 200, fmt='json')
    if resp:
        await msg.sendMessage([Plain(f'目前的最新版本为{resp["value"]["version"]}。\n下载地址：{resp["value"]["url"]}')])
