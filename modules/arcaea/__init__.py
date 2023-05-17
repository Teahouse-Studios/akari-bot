import os
import traceback

from config import Config
from core.builtins import Bot, ExecutionLockList
from core.builtins import Plain, Image
from core.component import module
from core.logger import Logger
from core.utils.http import get_url
from .dbutils import ArcBindInfoManager
from .getb30 import make_b30_img
from .info import get_info
from .initialize import arcb30init
from .song import get_song_info
from .utils import get_userinfo

arc = module('arcaea', developers=['OasisAkari'], desc='{arcaea.help.desc}',
             alias={'b30': 'arcaea b30', 'a': 'arcaea', 'arc': 'arcaea'})
webrender = Config('web_render')
assets_path = os.path.abspath('./assets/arcaea')
api = Config("botarcapi_url")
headers = {"Authorization": f'Bearer {Config("botarcapi_token")}'}
query_tasks = set()


class WithErrCode(Exception):
    pass


async def check_friendcode(msg: Bot.MessageSession, friendcode: str):
    if friendcode.isdigit():
        if len(friendcode) != 9:
            await msg.finish(msg.locale.t("arcaea.message.invalid.friendcode.non_digital"))
    else:
        await msg.finish(msg.locale.t("arcaea.message.invalid.friendcode.format"))


async def get_friendcode(msg: Bot.MessageSession):
    get_friendcode_from_db = ArcBindInfoManager(msg).get_bind_friendcode()
    if get_friendcode_from_db is not None:
        return get_friendcode_from_db


@arc.command('b30 [<friendcode>] {{arcaea.b30.help}}')
async def _(msg: Bot.MessageSession):
    if not os.path.exists(assets_path):
        await msg.finish(msg.locale.t("arcaea.message.assets.not_found", prefix=msg.prefixes[0]))
    query_code = None
    friendcode: str = msg.parsed_msg.get('<friendcode>', False)
    if friendcode:
        await check_friendcode(msg, friendcode)
    else:
        query_code = await get_friendcode(msg)
    if query_code is not None:
        try:
            if msg.target.senderId in query_tasks:
                await msg.finish(msg.locale.t("arcaea.b30.message.wait.already"))
            query_tasks.add(msg.target.senderId)
            get_ = await get_url(api + f'user/bests/session?user_name={query_code}', headers=headers,
                                 fmt='json')
            if get_['status'] == 0:
                await msg.sendMessage([Plain(msg.locale.t("arcaea.b30.message.wait")),
                                       Plain(msg.locale.t("arcaea.message.sb616")),
                                       Image(os.path.abspath('./assets/noc.jpg')),
                                       Image(os.path.abspath('./assets/aof.jpg'))])
            elif get_['status'] == -33:
                await msg.sendMessage(msg.locale.t("arcaea.b30.message.wait.cached"))
            ExecutionLockList.remove(msg)

            async def _get_result(session):
                try:
                    get_ = await get_url(api + f'user/bests/result?session_info={session}&with_song_info=true',
                                         headers=headers,
                                         fmt='json')
                    if get_['status'] in [-31, -32]:
                        Logger.warn(get_['message'])
                        return False
                    return get_
                except Exception as e:
                    Logger.error(e)
                    return False

            async def _check(msg: Bot.MessageSession, session, tried):
                if tried == 0:  # too lazy to make it short :rina:
                    await msg.sleep(15)
                    if _result := await _get_result(session):
                        return _result
                    await msg.sleep(15)
                    if _result := await _get_result(session):
                        return _result
                    await msg.sleep(15)
                    if _result := await _get_result(session):
                        return _result
                    await msg.sleep(15)
                    if _result := await _get_result(session):
                        return _result
                elif tried == 1:
                    await msg.sendMessage(msg.locale.t("arcaea.b30.message.wait.check"))
                    await msg.sleep(60)
                    if _result := await _get_result(session):
                        return _result
                elif tried <= 30:
                    await msg.sleep(60)
                    if _result := await _get_result(session):
                        return _result
                else:
                    await msg.sendMessage(msg.locale.t("arcaea.b30.message.wait.timeout"))
                    return False
                tried += 1
                return await _check(msg, session, tried)

            resp = await _check(msg, get_['content']['session_info'], 0)
            if resp:
                resp = await make_b30_img(resp)
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
                await msg.finish(msg.locale.t("arcaea.message.failed.fetch"))
        except Exception:
            traceback.print_exc()
            await msg.finish(msg.locale.t("arcaea.message.failed.fetch"))
        finally:
            query_tasks.remove(msg.target.senderId)
    else:
        await msg.finish(msg.locale.t("arcaea.message.user.unbound", prefix=msg.prefixes[0]))


@arc.command('info [<friendcode>] {{arcaea.info.help}}')
async def _(msg: Bot.MessageSession):
    if not os.path.exists(assets_path):
        await msg.sendMessage(msg.locale.t("arcaea.message.assets.not_found", prefix=msg.prefixes[0]))
        return
    query_code = None
    friendcode = msg.parsed_msg.get('<friendcode>', False)
    if friendcode:
        await check_friendcode(msg, friendcode)
    else:
        query_code = await get_friendcode(msg)
    if query_code is not None:
        try:
            resp = await get_info(msg, query_code)
            await msg.finish(resp)
        except Exception:
            traceback.print_exc()
            await msg.finish(msg.locale.t("arcaea.message.failed.fetch"))
    else:
        await msg.finish(msg.locale.t("arcaea.message.user.unbound", prefix=msg.prefixes[0]))


@arc.command('song <songname> <prs|pst|ftr|byd> {{arcaea.song.help}}')
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
    usercode = await get_friendcode(msg)
    await msg.finish(Plain(await get_song_info(msg, songname, diff, usercode)))


@arc.command('bind <friendcode|username> {{arcaea.bind.help}}')
async def _(msg: Bot.MessageSession):
    code: str = msg.parsed_msg['<friendcode|username>']
    getcode = await get_userinfo(code)
    if getcode:
        bind = ArcBindInfoManager(msg).set_bind_info(username=getcode[0], friendcode=getcode[1])
        if bind:
            await msg.finish(msg.locale.t("arcaea.bind.message.success", username=getcode[0], friendcode=getcode[1]))
    else:
        if code.isdigit():
            bind = ArcBindInfoManager(msg).set_bind_info(username='', friendcode=code)
            if bind:
                await msg.finish(msg.locale.t("arcaea.bind.message.success.but_failed_fetch_username"))
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
