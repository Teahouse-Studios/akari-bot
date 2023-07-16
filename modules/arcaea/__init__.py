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
             alias=['a', 'arc'])
webrender = Config('web_render')
assets_path = os.path.abspath('./assets/arcaea')
api = Config("botarcapi_url")
headers = {"Authorization": f'Bearer {Config("botarcapi_token")}'}
query_tasks = set()


class WithErrCode(Exception):
    pass


if api:

    @arc.command('b30 [<friend_code>] {{arcaea.help.b30}}')
    async def _(msg: Bot.MessageSession, friend_code: str = None):
        if not os.path.exists(assets_path):
            await msg.finish(msg.locale.t("arcaea.message.assets.not_found", prefix=msg.prefixes[0]))
        if friend_code is not None:
            if len(friend_code) != 9:
                await msg.finish(msg.locale.t("arcaea.message.invalid.friendcode.non_digital"))
            query_code = friend_code
        else:
            query_code = ArcBindInfoManager(msg).get_bind_friendcode()
        if query_code is not None:
            try:
                if msg.target.senderId in query_tasks:
                    await msg.finish(msg.locale.t("arcaea.message.b30.wait.already"))
                query_tasks.add(msg.target.senderId)
                get_ = await get_url(api + f'user/bests/session?user_name={query_code}', headers=headers,
                                     fmt='json')
                if get_['status'] == 0:
                    await msg.sendMessage(msg.locale.t("arcaea.message.b30.wait"))
                    if msg.target.targetFrom not in ['Discord|Channel', 'Telegram|group', 'Telegram|supergroup']:
                        await msg.sendMessage([Plain(msg.locale.t("arcaea.message.sb616")),
                                               Image(os.path.abspath('./assets/noc.jpg')),
                                               Image(os.path.abspath('./assets/aof.jpg'))])
                elif get_['status'] == -33:
                    await msg.sendMessage(msg.locale.t("arcaea.message.b30.wait.cached"))
                    if msg.target.targetFrom not in ['Discord|Channel', 'Telegram|group', 'Telegram|supergroup']:
                        await msg.sendMessage([Plain(msg.locale.t("arcaea.message.sb616")),
                                               Image(os.path.abspath('./assets/noc.jpg')),
                                               Image(os.path.abspath('./assets/aof.jpg'))])
                elif get_['status'] == -23:
                    await msg.finish(msg.locale.t("arcaea.message.b30.low_potential"))
                else:
                    await msg.finish(msg.locale.t("arcaea.message.get_failed") + get_['message'])
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
                    if tried == 0:
                        for _ in range(4):
                            await msg.sleep(15)
                            if _result := await _get_result(session):
                                return _result
                    elif tried == 1:
                        await msg.sendMessage(msg.locale.t("arcaea.message.b30.wait.check"))
                        await msg.sleep(60)
                        if _result := await _get_result(session):
                            return _result
                    elif tried <= 30:
                        await msg.sleep(60)
                        if _result := await _get_result(session):
                            return _result
                    else:
                        await msg.sendMessage(msg.locale.t("arcaea.message.b30.wait.timeout"))
                        return False
                    tried += 1
                    return await _check(msg, session, tried)

                resp = await _check(msg, get_['content']['session_info'], 0)
                if resp:
                    resp = await make_b30_img(resp)
                    if resp['status']:
                        msgchain = [Plain(msg.locale.t("arcaea.message.b30.success", b30=resp["b30"], r10=resp["r10"],
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
                    await msg.finish(msg.locale.t("arcaea.message.get_failed") + err_msg)
                else:
                    await msg.finish(msg.locale.t("arcaea.message.get_failed"))
            except Exception:
                traceback.print_exc()
                await msg.finish(msg.locale.t("arcaea.message.get_failed"))
            finally:
                query_tasks.remove(msg.target.senderId)
        else:
            await msg.finish(msg.locale.t("arcaea.message.user_unbound", prefix=msg.prefixes[0]))

    @arc.command('info [<friend_code>] {{arcaea.help.info}}')
    async def _(msg: Bot.MessageSession, friend_code: int = None):
        if not os.path.exists(assets_path):
            await msg.sendMessage(msg.locale.t("arcaea.message.assets.not_found", prefix=msg.prefixes[0]))
            return
        if friend_code is not None:
            if len(str(friend_code)) != 9:
                await msg.finish(msg.locale.t("arcaea.message.invalid.friendcode.non_digital"))
            query_code = friend_code
        else:
            query_code = ArcBindInfoManager(msg).get_bind_friendcode()
        if query_code is not None:
            try:
                resp = await get_info(msg, query_code)
                await msg.finish(resp)
            except Exception:
                traceback.print_exc()
                await msg.finish(msg.locale.t("arcaea.message.get_failed"))
        else:
            await msg.finish(msg.locale.t("arcaea.message.user_unbound", prefix=msg.prefixes[0]))

    @arc.command('song <songname> [<diff>] {{arcaea.help.song}}')
    async def _(msg: Bot.MessageSession):
        songname = msg.parsed_msg['<songname>']
        diff_ = msg.parsed_msg.get('<diff>')
        if not diff_:
            diff_ = 'FTR'

        s = diff_.upper()
        if s in ['PST', 'PAST']:
            diff = 0
        elif s in ['PRS', 'PRESENT']:
            diff = 1
        elif s in ['FTR', 'FUTURE']:
            diff = 2
        elif s in ['BYD', 'BEYOND']:
            diff = 3
        else:
            await msg.finish(msg.locale.t("arcaea.message.song.invalid.difficulty"))

        usercode = ArcBindInfoManager(msg).get_bind_friendcode()
        await msg.finish(Plain(await get_song_info(msg, songname, diff, usercode)))

    @arc.command('bind <friendcode|username> {{arcaea.help.bind}}')
    async def _(msg: Bot.MessageSession):
        code: str = msg.parsed_msg['<friendcode|username>']
        getcode = await get_userinfo(code)
        if getcode:
            bind = ArcBindInfoManager(msg).set_bind_info(username=getcode[0], friendcode=getcode[1])
            if bind:
                await msg.finish(msg.locale.t("arcaea.message.bind.success", username=getcode[0], friendcode=getcode[1]))
        else:
            if code.isdigit():
                bind = ArcBindInfoManager(msg).set_bind_info(username='', friendcode=code)
                if bind:
                    await msg.finish(msg.locale.t("arcaea.message.bind.success.but_failed_fetch_username"))
            else:
                await msg.finish(msg.locale.t("arcaea.message.bind.failed"))

    @arc.command('unbind {{arcaea.help.unbind}}')
    async def _(msg: Bot.MessageSession):
        unbind = ArcBindInfoManager(msg).remove_bind_info()
        if unbind:
            await msg.finish(msg.locale.t("arcaea.message.unbind.success"))

    @arc.command('initialize', required_superuser=True)
    async def _(msg: Bot.MessageSession):
        assets_apk = os.path.abspath('./assets/arc.apk')
        if not os.path.exists(assets_apk):
            await msg.finish(msg.locale.t("arcaea.message.initialize.not_found"))
            return
        result = await arcb30init()
        if result:
            await msg.finish(msg.locale.t("arcaea.message.initialize.success"))


@arc.command('download {{arcaea.help.download}}')
async def _(msg: Bot.MessageSession):
    if not webrender:
        await msg.finish([msg.locale.t("arcaea.message.no_webrender")])
    resp = await get_url(webrender + 'source?url=https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/', 200,
                         fmt='json')
    if resp:
        await msg.finish([Plain(msg.locale.t("arcaea.message.download.success", version=resp["value"]["version"],
                                             url=resp['value']['url']))])


@arc.command('random {{arcaea.help.random}}')
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


@arc.command('rank free {{arcaea.help.rank.free}}', 'rank paid {{arcaea.help.rank.paid}}')
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
