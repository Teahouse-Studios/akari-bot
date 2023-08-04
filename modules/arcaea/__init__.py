import os
import traceback

from config import Config
from core.builtins import Bot, ExecutionLockList
from core.builtins import Plain, Image
from core.component import module
from core.logger import Logger
from core.utils.http import get_url

arc = module('arcaea', developers=['OasisAkari'], desc='{arcaea.help.desc}',
             alias=['a', 'arc'])
webrender = Config('web_render')
assets_path = os.path.abspath('./assets/arcaea')


class WithErrCode(Exception):
    pass


@arc.command('b30 [<friend_code>] {{arcaea.help.b30}}')
@arc.command('info [<friend_code>] {{arcaea.help.info}}')
@arc.command('song <songname> [<diff>] {{arcaea.help.song}}')
@arc.command('bind <friendcode|username> {{arcaea.help.bind}}')
@arc.command('unbind {{arcaea.help.unbind}}')
async def _(msg: Bot.MessageSession):
    await msg.sendMessage([Plain(msg.locale.t("arcaea.message.sb616")),
                           Image(os.path.abspath('./assets/noc.jpg'))])


@arc.command('download {{arcaea.help.download}}')
async def _(msg: Bot.MessageSession):
    if not webrender:
        await msg.finish([msg.locale.t("arcaea.message.no_webrender")])
    resp = await get_url(webrender + '/source?url=https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/', 200,
                         fmt='json')
    if resp:
        await msg.finish([Plain(msg.locale.t("arcaea.message.download.success", version=resp["value"]["version"],
                                             url=resp['value']['url']))])


@arc.command('random {{arcaea.help.random}}')
async def _(msg: Bot.MessageSession):
    if not webrender:
        await msg.finish([msg.locale.t("arcaea.message.no_webrender")])
    resp = await get_url(webrender + '/source?url=https://webapi.lowiro.com/webapi/song/showcase/', 200, fmt='json')
    if resp:
        value = resp["value"][0]
        image = f'{assets_path}/jacket/{value["song_id"]}.jpg'
        result = [Plain(value["title"]["en"])]
        if os.path.exists(image):
            result.append(Image(path=image))
        await msg.finish(result)


@arc.command('rank free {{arcaea.help.rank.free}}', 'rank paid {{arcaea.help.rank.paid}}')
async def _(msg: Bot.MessageSession):
    if not webrender:
        await msg.finish([msg.locale.t("arcaea.message.no_webrender")])
    if msg.parsed_msg.get('free', False):
        resp = await get_url(webrender + '/source?url=https://webapi.lowiro.com/webapi/song/rank/free/', 200, fmt='json')
    else:
        resp = await get_url(webrender + '/source?url=https://webapi.lowiro.com/webapi/song/rank/paid/', 200, fmt='json')
    if resp:
        r = []
        rank = 0
        for x in resp['value']:
            rank += 1
            r.append(f'{rank}. {x["title"]["en"]} ({x["status"]})')
        await msg.finish('\n'.join(r))
