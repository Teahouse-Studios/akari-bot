import os

from config import Config
from core.builtins import Bot
from core.builtins import Image, Plain
from core.utils.http import get_url
from core.component import module

webrender = Config('web_render')
arc = module('arcaea', developers=['OasisAkari'], desc='{arcaea.help.desc}',
             alias={'b30': 'arcaea b30', 'a': 'arcaea', 'arc': 'arcaea'})
assets_path = os.path.abspath('./assets/')


@arc.handle()
async def _(msg: Bot.MessageSession):
    await msg.finish([msg.locale.t("arcaea.message.sb616"), Image(assets_path + '/noc.jpg'), Image(assets_path + '/aof.jpg')])


@arc.command('download {{arcaea.download.help}}')
async def _(msg: Bot.MessageSession):
    if not webrender:
        await msg.finish([msg.locale.t("arcaea.message.no_webrender")])
    resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/', 200,
                         fmt='json')
    if resp:
        await msg.finish([Plain(msg.locale.t("arcaea.download.message.success", version=resp["value"]["version"],
                                             url=resp['value']['url']))])


@arc.command('random {{arcaea.random.help}}')
async def _(msg: Bot.MessageSession):
    if not webrender:
        await msg.finish([msg.locale.t("arcaea.message.no_webrender")])
    resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/song/showcase/', 200, fmt='json')
    if resp:
        value = resp["value"][0]
        image = f'{assets_path}/jacket/{value["song_id"]}.jpg'
        result = [Plain(value["title"]["en"])]
        if os.path.exists(image):
            result.append(Image(path=image))
        await msg.finish(result)


@arc.command('rank free {{arcaea.rank.help.free}}', 'rank paid {{arcaea.rank.help.paid}}')
async def _(msg: Bot.MessageSession):
    if not webrender:
        await msg.finish([msg.locale.t("arcaea.message.no_webrender")])
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
