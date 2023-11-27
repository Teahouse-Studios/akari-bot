import os

import urllib.parse

from config import CFG
from core.builtins import Bot, Image, Plain
from core.component import module
from core.logger import Logger
from core.utils.http import get_url

assets_path = os.path.abspath('./assets/arcaea')
web_render = CFG.get_url('web_render')
web_render_local = CFG.get_url('web_render_local')


arc = module('arcaea', developers=['OasisAkari'], desc='{arcaea.help.desc}',
             alias=['a', 'arc'])

class WithErrCode(Exception):
    pass


@arc.command('b30')
async def _(msg: Bot.MessageSession):
    await msg.send_message([Plain(msg.locale.t("arcaea.message.sb616")),
                            Image(os.path.abspath('./assets/arcaea/noc.jpg'))])


@arc.command('download {{arcaea.help.download}}')
async def _(msg: Bot.MessageSession, use_local=True):
    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
            await msg.finish(msg.locale.t("error.webrender.unconfigured"))
        use_local = False
    resp = await get_url((web_render_local if use_local else web_render) + 'source?url=' +
                         urllib.parse.quote('https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/'), 200,
                         fmt='json')
    if resp:
        await msg.finish([Plain(msg.locale.t("arcaea.message.download", version=resp["value"]["version"],
                                             url=resp['value']['url']))])
    else:
        await msg.finish(msg.locale.t("arcaea.message.get_failed"))


@arc.command('random {{arcaea.help.random}}')
async def _(msg: Bot.MessageSession, use_local=True):
    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
            await msg.finish(msg.locale.t("error.webrender.unconfigured"))
        use_local = False
    resp = await get_url((web_render_local if use_local else web_render) + 'source?url=' +
                         urllib.parse.quote('https://webapi.lowiro.com/webapi/song/showcase/'),
                         200, fmt='json')
    if resp:
        value = resp["value"][0]
        image = f'{assets_path}/jacket/{value["song_id"]}.jpg'
        result = [Plain(value["title"]["en"])]
        if os.path.exists(image):
            result.append(Image(path=image))
        await msg.finish(result)
    else:
        await msg.finish(msg.locale.t("arcaea.message.get_failed"))


@arc.command('rank free {{arcaea.help.rank.free}}', 'rank paid {{arcaea.help.rank.paid}}')
async def _(msg: Bot.MessageSession, use_local=True):
    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
            await msg.finish(msg.locale.t("error.webrender.unconfigured"))
        use_local = False
    if msg.parsed_msg.get('free', False):
        resp = await get_url((web_render_local if use_local else web_render) + 'source?url=' +
                             urllib.parse.quote('https://webapi.lowiro.com/webapi/song/rank/free/'),
                             200, fmt='json')
    else:
        resp = await get_url((web_render_local if use_local else web_render) + 'source?url=' +
                             urllib.parse.quote('https://webapi.lowiro.com/webapi/song/rank/paid/'), 200, fmt='json')
    if resp:
        r = []
        rank = 0
        for x in resp['value']:
            rank += 1
            r.append(f'{rank}. {x["title"]["en"]} ({x["status"]})')
        await msg.finish('\n'.join(r))
    else:
        await msg.finish(msg.locale.t("arcaea.message.get_failed"))
