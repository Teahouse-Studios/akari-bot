import os
import traceback

from config import Config
from core.builtins import Bot
from core.builtins import Plain, Image
from core.component import module
from core.utils.http import get_url
from .dbutils import ArcBindInfoManager
from .getb30 import getb30
from .getb30_official import getb30_official
from .info import get_info
from .info_official import get_info_official
from .initialize import arcb30init
from .song import get_song_info
from .utils import get_userinfo

arc = module('arcaea', developers=['OasisAkari'], desc='{arcaea.help.desc}',
             alias={'b30': 'arcaea b30', 'a': 'arcaea', 'arc': 'arcaea'})
webrender = Config('web_render')
assets_path = os.path.abspath('./assets/arcaea')


class WithErrCode(Exception):
    pass


@arc.command('b30 [<friendcode>] {{arcaea.b30.help}}',
             'b30 official [<friendcode>] {{arcaea.message.official}}',
             'b30 unofficial [<friendcode>] {{arcaea.message.unofficial}}')
async def _(msg: Bot.MessageSession):
    if not os.path.exists(assets_path):
        await msg.finish(msg.locale.t("arcaea.message.assets.not_found", prefix=msg.prefixes[0]))
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
                await msg.finish(msg.locale.t("arcaea.message.invalid.friendcode.non_digital"))
        else:
            await msg.finish(msg.locale.t("arcaea.message.invalid.friendcode.format"))
    else:
        get_friendcode_from_db = ArcBindInfoManager(msg).get_bind_friendcode()
        if get_friendcode_from_db is not None:
            query_code = get_friendcode_from_db
    if query_code is not None:
        if not unofficial:
            try:
                resp = await getb30_official(query_code)
                if resp["status"]:
                    msgchain = [Plain(msg.locale.t("arcaea.b30.message.success", b30=resp["b30"], r10=resp["r10"],
                                                   last5list=resp["last5list"]))]
                    if 'file' in resp and msg.Feature.image:
                        msgchain.append(Image(path=resp['file']))
                    await msg.sendMessage(msgchain, allow_split_image=False)
                else:
                    raise
            except Exception:
                traceback.print_exc()
                if not official and prefer_uses is None:
                    await msg.sendMessage(msg.locale.t("arcaea.message.official.fetch.failed.fallback"))
                    unofficial = True
                else:
                    await msg.finish(msg.locale.t("arcaea.message.official.fetch.failed"))
        if unofficial:
            try:
                resp = await getb30(query_code)
                if resp['status']:
                    msgchain = [Plain(msg.locale.t("arcaea.b30.message.success", b30=resp["b30"], r10=resp["r10"],
                                                   last5list=resp["last5list"]))]
                    if 'file' in resp and msg.Feature.image:
                        msgchain.append(Image(path=resp['file']))
                    await msg.finish(msgchain)
                else:
                    if 'errcode' in resp:
                        raise WithErrCode(resp['errcode'])
                    else:
                        raise
            except WithErrCode as e:
                err_key = "arcaea.errcode." + str(e.args[0])
                err_msg = msg.locale.t(err_key)
                if err_key != err_msg:
                    await msg.finish(msg.locale.t("arcaea.message.failed.fetch") + err_msg)
                else:
                    await msg.finish(msg.locale.t("arcaea.message.unofficial.fetch.failed"))
            except Exception:
                traceback.print_exc()
                await msg.finish(msg.locale.t("arcaea.message.unofficial.fetch.failed"))
    else:
        await msg.finish(msg.locale.t("arcaea.message.user.unbound", prefix=msg.prefixes[0]))


@arc.command('info [<friendcode>] {{arcaea.info.help}}',
             'info official [<friendcode>] {{arcaea.message.official}}',
             'info unofficial [<friendcode>] {{arcaea.message.unofficial}}', )
async def _(msg: Bot.MessageSession):
    if not os.path.exists(assets_path):
        await msg.sendMessage(msg.locale.t("arcaea.message.assets.not_found", prefix=msg.prefixes[0]))
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
                await msg.finish(msg.locale.t("arcaea.message.invalid.friendcode.non_digital"))
        else:
            await msg.finish(msg.locale.t("arcaea.message.invalid.friendcode.format"))
    else:
        get_friendcode_from_db = ArcBindInfoManager(msg).get_bind_friendcode()
        if get_friendcode_from_db is not None:
            query_code = get_friendcode_from_db
    if query_code is not None:
        if not unofficial:
            try:
                resp = await get_info_official(msg, query_code)
                if resp['success']:
                    await msg.finish(resp['msg'])
                else:
                    if not official and prefer_uses is None:
                        await msg.sendMessage(msg.locale.t("arcaea.message.official.fetch.failed.fallback"))
                        unofficial = True
            except Exception:
                traceback.print_exc()
                if not official and prefer_uses is None:
                    await msg.sendMessage(msg.locale.t("arcaea.message.official.fetch.failed.fallback"))
                    unofficial = True
        if unofficial:
            try:
                resp = await get_info(msg, query_code)
                await msg.finish(resp)
            except Exception:
                traceback.print_exc()
                await msg.finish(msg.locale.t("arcaea.message.unofficial.fetch.failed"))
    else:
        await msg.finish(msg.locale.t("arcaea.message.user.unbound", prefix=msg.prefixes[0]))


@arc.command('song <songname+prs/pst/byd> {{arcaea.song.help}}')
async def _(msg: Bot.MessageSession):
    songname_ = msg.parsed_msg.get('<songname+prs/pst/byd>', False)
    songname_split = songname_.split(' ')
    diff = -1
    for s in songname_split:
        s_ = s.lower()
        if s_ == 'pst':
            diff = 0
        elif s_ == 'prs':
            diff = 1
        elif s_ == 'ftr':
            diff = 2
        elif s_ == 'byd':
            diff = 3
        if diff != -1:
            songname_split.remove(s)
            break
    if diff == -1:
        await msg.finish(msg.locale.t("arcaea.song.message.invalid.difficulty"))
    songname = ' '.join(songname_split)
    usercode = None
    get_friendcode_from_db = ArcBindInfoManager(msg).get_bind_friendcode()
    if get_friendcode_from_db is not None:
        usercode = get_friendcode_from_db
    await msg.finish(Plain(await get_song_info(msg, songname, diff, usercode)))


@arc.command('bind <friendcode/username> {{arcaea.bind.help}}')
async def _(msg: Bot.MessageSession):
    code: str = msg.parsed_msg['<friendcode/username>']
    getcode = await get_userinfo(code)
    if getcode:
        bind = ArcBindInfoManager(msg).set_bind_info(username=getcode[0], friendcode=getcode[1])
        if bind:
            await msg.finish(msg.locale.t("arcaea.message.bind.success", username=getcode[0], friendcode=getcode[1]))
    else:
        if code.isdigit():
            bind = ArcBindInfoManager(msg).set_bind_info(username='', friendcode=code)
            if bind:
                await msg.finish(msg.locale.t("arcaea.bind.message.success.but.failed.fetch.username"))
        else:
            await msg.finish(msg.locale.t("arcaea.bind.message.failed"))


@arc.command('unbind {{arcaea.unbind.help}}')
async def _(msg: Bot.MessageSession):
    unbind = ArcBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish(msg.locale.t("arcaea.unbind.message.success"))


@arc.command('initialize', required_superuser=True)
async def _(msg: Bot.MessageSession):
    assets_apk = os.path.abspath('./assets/arc.apk')
    if not os.path.exists(assets_apk):
        await msg.finish(msg.locale.t("arcaea.initialize.message.not_found"))
        return
    result = await arcb30init()
    if result:
        await msg.finish(msg.locale.t("arcaea.initialize.message.success"))


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


@arc.command('switch {{arcaea.switch.help}}')
async def _(msg: Bot.MessageSession):
    value = msg.options.get('arc_api', True)
    set_value = msg.data.edit_option('arc_api', not value)
    await msg.finish(msg.locale.t("arcaea.switch.message.success.official"
                                  if not value else "arcaea.switch.message.success.unofficial"))
