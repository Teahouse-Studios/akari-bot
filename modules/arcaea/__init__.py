import os
import traceback

from config import Config
from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Plain, Image
from core.utils import get_url
from .dbutils import ArcBindInfoManager
from .getb30 import getb30
from .getb30_official import getb30_official
from .info import get_info
from .info_official import get_info_official
from .initialize import arcb30init
from .song import get_song_info
from .utils import get_userinfo

arc = on_command('arcaea', developers=['OasisAkari'], desc='查询Arcaea相关内容。',
                 alias={'b30': 'arcaea b30', 'a': 'arcaea', 'arc': 'arcaea'})
webrender = Config('web_render')
assets_path = os.path.abspath('./assets/arcaea')


@arc.handle('b30 [<friendcode>] {查询一个Arcaea用户的b30列表（自动选择使用API）}',
            'b30 official [<friendcode>] {使用官方API}',
            'b30 unofficial [<friendcode>] {使用非官方API}')
async def _(msg: MessageSession):
    if not os.path.exists(assets_path):
        await msg.finish('未找到资源文件！请放置一枚arcaea的apk到机器人的assets目录并重命名为arc.apk后，使用~arcaea initialize初始化资源。')
    query_code = None
    prefer_uses = msg.options.get('arc_api', None)
    official = msg.parsed_msg.get('official', False)
    unofficial = msg.parsed_msg.get('unofficial', False)
    if not unofficial and not official and prefer_uses is False:
        unofficial = True
    if not official and prefer_uses is True:
        official = True

    friendcode: str = msg.parsed_msg.get('<friendcode>', False)
    if friendcode:
        if friendcode.isdigit():
            if len(friendcode) == 9:
                query_code = friendcode
            else:
                await msg.finish('好友码必须是9位数字！')
        else:
            await msg.finish('请输入正确的好友码！')
    else:
        get_friendcode_from_db = ArcBindInfoManager(msg).get_bind_friendcode()
        if get_friendcode_from_db is not None:
            query_code = get_friendcode_from_db
    if query_code is not None:
        if not unofficial:
            try:
                resp = await getb30_official(query_code)
                msgchain = [Plain(resp['text'])]
                if 'file' in resp and msg.Feature.image:
                    msgchain.append(Image(path=resp['file']))
                await msg.sendMessage(msgchain, allow_split_image=False)
            except Exception:
                traceback.print_exc()
                if not official and prefer_uses is None:
                    await msg.sendMessage('使用官方API获取失败，尝试使用非官方接口。')
                    unofficial = True
                else:
                    await msg.finish('使用官方API获取失败。')
        if unofficial:
            try:
                resp = await getb30(query_code)
                msgchain = [Plain(resp['text'])]
                if 'file' in resp and msg.Feature.image:
                    msgchain.append(Image(path=resp['file']))
                await msg.finish(msgchain)
            except Exception:
                traceback.print_exc()
                await msg.finish('使用非官方API获取失败。')
    else:
        await msg.finish('未绑定用户，请使用~arcaea bind <friendcode>绑定一个用户。')


@arc.handle('info [<friendcode>] {查询一个Arcaea用户的最近游玩记录}',
            'info official [<friendcode>] {使用官方API}',
            'info unofficial [<friendcode>] {使用非官方API}',)
async def _(msg: MessageSession):
    if not os.path.exists(assets_path):
        await msg.sendMessage('未找到资源文件！请放置一枚arcaea的apk到机器人的assets目录并重命名为arc.apk后，使用~arcaea initialize初始化资源。')
        return
    query_code = None
    prefer_uses = msg.options.get('arc_api', None)
    unofficial = msg.parsed_msg.get('unofficial', False)
    official = msg.parsed_msg.get('official', False)
    if not unofficial and not official and prefer_uses is False:
        unofficial = True

    if not official and prefer_uses is True:
        official = True
    friendcode = msg.parsed_msg.get('<friendcode>', False)
    if friendcode:
        if friendcode.isdigit():
            if len(friendcode) == 9:
                query_code = friendcode
            else:
                await msg.finish('好友码必须是9位数字！')
        else:
            await msg.finish('请输入正确的好友码！')
    else:
        get_friendcode_from_db = ArcBindInfoManager(msg).get_bind_friendcode()
        if get_friendcode_from_db is not None:
            query_code = get_friendcode_from_db
    if query_code is not None:
        if not unofficial:
            try:
                resp = await get_info_official(query_code)
                if resp['success']:
                    await msg.finish(resp['msg'])
                else:
                    if not official and prefer_uses is None:
                        await msg.sendMessage('使用官方API获取失败，尝试使用非官方接口。')
                        unofficial = True
            except Exception:
                traceback.print_exc()
                if not official and prefer_uses is None:
                    await msg.sendMessage('使用官方API获取失败，尝试使用非官方接口。')
                    unofficial = True
        if unofficial:
            try:
                resp = await get_info(query_code)
                await msg.finish(resp)
            except Exception:
                traceback.print_exc()
                await msg.finish('使用非官方API获取失败。')
    else:
        await msg.finish('未绑定用户，请使用~arcaea bind <friendcode>绑定一个用户。')


@arc.handle('song <songname+prs/pst/byd> {查询一首Arcaea谱面的信息}')
async def _(msg: MessageSession):
    songname_ = msg.parsed_msg.get('<songname+prs/pst/byd>', False)
    songname_split = songname_.split(' ')
    diff = -1
    for s in songname_split:
        s = s.lower()
        if s == 'prs':
            diff = 0
        elif s == 'pst':
            diff = 1
        elif s == 'ftr':
            diff = 2
        elif s == 'byd':
            diff = 3
        if diff != -1:
            songname_split.remove(s)
            break
    if diff == -1:
        await msg.finish('请输入正确的谱面难度！')
    songname = ' '.join(songname_split)
    usercode = None
    get_friendcode_from_db = ArcBindInfoManager(msg).get_bind_friendcode()
    if get_friendcode_from_db is not None:
        usercode = get_friendcode_from_db
    await msg.finish(Plain(await get_song_info(songname, diff, usercode)))


@arc.handle('bind <friendcode/username> {绑定一个Arcaea用户}')
async def _(msg: MessageSession):
    code: str = msg.parsed_msg['<friendcode/username>']
    getcode = await get_userinfo(code)
    if getcode:
        bind = ArcBindInfoManager(msg).set_bind_info(username=getcode[0], friendcode=getcode[1])
        if bind:
            await msg.finish(f'绑定成功：{getcode[0]}({getcode[1]})')
    else:
        if code.isdigit():
            bind = ArcBindInfoManager(msg).set_bind_info(username='', friendcode=code)
            if bind:
                await msg.finish('绑定成功，但是无法获取用户信息。请自行检查命令是否可用。')
        else:
            await msg.finish('绑定失败，请尝试使用好友码绑定。')


@arc.handle('unbind {取消绑定用户}')
async def _(msg: MessageSession):
    unbind = ArcBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish('取消绑定成功。')


@arc.handle('initialize', required_superuser=True)
async def _(msg: MessageSession):
    assets_apk = os.path.abspath('./assets/arc.apk')
    if not os.path.exists(assets_apk):
        await msg.finish('未找到arc.apk！')
        return
    result = await arcb30init()
    if result:
        await msg.finish('成功初始化！')


@arc.handle('download {获取最新版本的游戏apk}')
async def _(msg: MessageSession):
    if not webrender:
        await msg.finish(['未配置webrender，无法使用此命令。'])
    resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/', 200,
                         fmt='json')
    if resp:
        await msg.finish([Plain(f'目前的最新版本为{resp["value"]["version"]}。\n下载地址：{resp["value"]["url"]}')])


@arc.handle('random {随机一首曲子}')
async def _(msg: MessageSession):
    if not webrender:
        await msg.finish(['未配置webrender，无法使用此命令。'])
    resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/song/showcase/', 200, fmt='json')
    if resp:
        value = resp["value"][0]
        image = f'{assets_path}/jacket/{value["song_id"]}.jpg'
        result = [Plain(value["title"]["en"])]
        if os.path.exists(image):
            result.append(Image(path=image))
        await msg.finish(result)


@arc.handle('rank free {查看当前免费包游玩排行}', 'rank paid {查看当前付费包游玩排行}')
async def _(msg: MessageSession):
    if not webrender:
        await msg.finish(['未配置webrender，无法使用此命令。'])
    if msg.parsed_msg.get('free', False):
        resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/song/rank/free/', 200, fmt='json')
    else:
        resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/song/rank/paid/', 200, fmt='json')
    if resp:
        r = []
        rank = 0
        for x in resp['value']:
            rank += 1
            r.append(f'{rank}. {x["title"]["en"]} ({x["status"]})')
        await msg.finish('\n'.join(r))


@arc.handle('switch {切换查询时默认优先使用的API接口}')
async def _(msg: MessageSession):
    value = msg.options.get('arc_api', True)
    set_value = msg.data.edit_option('arc_api', not value)
    await msg.finish(f'已切换为{"官方" if not value else "非官方"}API。')
