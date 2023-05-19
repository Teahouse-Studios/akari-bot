"""
This service utilizes API functionality provided by and with permission from lowiro. It is not affiliated with or endorsed by lowiro.
"""
import os
import traceback
from datetime import datetime

from config import Config
from core.builtins import Plain
from core.logger import Logger
from core.utils.http import get_url

assets_path = os.path.abspath('./assets/arcaea')
apiurl = Config('arcapi_official_url')
headers = {'Authorization': Config('arcapi_official_token')}
headers_botarcapi = {"User-Agent": Config('botarcapi_agent')}
botarcapi_url = Config('botarcapi_url')


async def get_songinfo(songid):
    try:
        get_songinfo_from_botarcapi = await get_url(f'{botarcapi_url}song/info?songid={songid}',
                                                    headers=headers_botarcapi, status_code=200, fmt='json')
        return get_songinfo_from_botarcapi['content']
    except Exception:
        traceback.print_exc()
        return False


async def get_info_official(msg, usercode):
    try:
        getuserinfo_json = await get_url(f'{apiurl}user/{usercode}', headers=headers, status_code=200, fmt='json')
    except ValueError as e:
        Logger.info(f'[{usercode}] {e}')
        return {'success': False, 'msg': msg.finish(msg.locale.t('arcaea.message.failed'))}
    except Exception:
        traceback.print_exc()
        return {'success': False, 'msg': msg.finish(msg.locale.t('arcaea.message.failed'))}
    getuserinfo = getuserinfo_json['data']
    username = getuserinfo['display_name']
    potential = getuserinfo['potential']
    if potential is not None:
        potential = int(potential) / 100
    else:
        potential = '--'
    recent = getuserinfo["last_played_song"]
    if recent is None:
        return [Plain(msg.finish(msg.locale.t('arcaea.message.info.result.none')))]
    difficulty = '???'
    if recent['difficulty'] == 0:
        difficulty = 'PST'
    elif recent['difficulty'] == 1:
        difficulty = 'PRS'
    elif recent['difficulty'] == 2:
        difficulty = 'FTR'
    elif recent['difficulty'] == 3:
        difficulty = 'BYD'
    score = recent['score']
    ptt = realptt = '???'
    trackname = recent['song_id']
    songinfo = await get_songinfo(recent['song_id'])
    if songinfo:
        s = songinfo['difficulties'][recent['difficulty']]
        trackname = s['name_en']
        realptt = s['rating'] / 10
        ptt = realptt
        if score >= 10000000:
            ptt += 2
        elif score >= 9800000:
            ptt += 1 + (score - 9800000) / 200000
        else:
            ptt += (score - 9500000) / 300000

    shiny_pure = recent['shiny_pure_count']
    pure = recent['pure_count']
    far = recent['far_count']
    lost = recent['lost_count']
    time_played = datetime.fromtimestamp(recent['time_played'] / 1000)
    result = {
        'success': True,
        'msg': msg.locale.t(
            'arcaea.message.info.result',
            username=username,
            potential=potential,
            trackname=trackname,
            difficulty=difficulty,
            score=score,
            pure=pure,
            shiny_pure=shiny_pure,
            far=far,
            lost=lost,
            realptt=realptt,
            ptt=ptt,
            time_played=time_played.strftime("%Y-%m-%d %H:%M:%S"))}
    return result
