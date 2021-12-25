import os
import traceback

from config import Config
from core.component import on_command
from core.elements import MessageSession, Plain, Image
from core.utils import get_url
from .getb30 import getb30
from .info import get_info
from .initialize import arcb30init

arc = on_command('arcaea', developers=['OasisAkari'], desc='查询Arcaea相关内容。',
                 alias={'b30': 'arcaea b30', 'a': 'arcaea', 'arc': 'arcaea'})
webrender = Config('web_render')
assets_path = os.path.abspath('./assets/arcaea')


@arc.handle('b30 <friendcode> {查询一个Arcaea用户的b30列表}')
async def _(msg: MessageSession):
    assets = os.path.abspath('assets/arcaea')
    if not os.path.exists(assets):
        await msg.sendMessage('未找到资源文件！请放置一枚arcaea的apk到机器人的assets目录并重命名为arc.apk后，使用~arcaea initialize初始化资源。')
        return
    friendcode = msg.parsed_msg['<friendcode>']
    if friendcode:
        try:
            resp = await getb30(friendcode)
        except Exception:
            traceback.print_exc()
            await msg.sendMessage('获取失败。')
            return
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
    try:
        resp = await get_info(friendcode)
    except Exception:
        traceback.print_exc()
        await msg.sendMessage('获取失败。')
        return
    await msg.sendMessage(resp)


@arc.handle('initialize', required_superuser=True)
async def _(msg: MessageSession):
    assets_apk = os.path.abspath('./assets/arc.apk')
    if not os.path.exists(assets_apk):
        await msg.sendMessage('未找到arc.apk！')
        return
    result = await arcb30init()
    if result:
        await msg.sendMessage('成功初始化！')


@arc.handle('download {获取最新版本的游戏apk}')
async def _(msg: MessageSession):
    resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/', 200, fmt='json')
    if resp:
        await msg.sendMessage([Plain(f'目前的最新版本为{resp["value"]["version"]}。\n下载地址：{resp["value"]["url"]}')])


@arc.handle('random {随机一首曲子}')
async def _(msg: MessageSession):
    resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/song/showcase/', 200, fmt='json')
    if resp:
        value = resp["value"][0]
        image = f'{assets_path}/jacket/{value["song_id"]}.jpg'
        result = [Plain(value["title"]["en"])]
        if os.path.exists(image):
            result.append(Image(path=image))
        await msg.sendMessage(result)


@arc.handle(['rank free {查看当前免费包游玩排行}', 'rank paid {查看当前付费包游玩排行}'])
async def _(msg: MessageSession):
    if msg.parsed_msg['free']:
        resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/song/rank/free/', 200, fmt='json')
    else:
        resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/song/rank/paid/', 200, fmt='json')
    if resp:
        r = []
        rank = 0
        for x in resp['value']:
            rank += 1
            r.append(f'{rank}. {x["title"]["en"]} ({x["status"]})')
        await msg.sendMessage('\n'.join(r))