import asyncio
import os
import traceback
from datetime import datetime

from config import Config
from core.builtins import Plain, Image
from core.logger import Logger
from core.utils.http import get_url
from modules.arcaea.utils import autofix_b30_song_background, errcode

assets_path = os.path.abspath('./assets/arcaea')
api_url = Config("botarcapi_url")


async def get_info(usercode):
    headers = {"User-Agent": Config('botarcapi_agent')}
    try:
        get_ = await get_url(api_url + f"user/info?usercode={usercode}&recent=1&withsonginfo=True",
                             status_code=200,
                             headers=headers,
                             fmt='json')
    except ValueError as e:
        return [Plain(msg.locale.t('arcaea.message.failed.errcode') + str(e))]
    except Exception:
        traceback.print_exc()
        return [Plain(msg.locale.t('arcaea.message.failed'))]
    Logger.debug(get_)
    if get_["status"] == 0:
        recent = get_['content']["recent_score"]
        if len(recent) < 0:
            return [Plain(msg.locale.t('arcaea.info.message.result.none'))]
        recent = recent[0]
        difficulty = '???'
        if recent['difficulty'] == 0:
            difficulty = 'PST'
        elif recent['difficulty'] == 1:
            difficulty = 'PRS'
        elif recent['difficulty'] == 2:
            difficulty = 'FTR'
        elif recent['difficulty'] == 3:
            difficulty = 'BYD'
        songinfo = get_['content']['songinfo'][0]
        trackname = songinfo['name_en']
        imgpath = f'{assets_path}/jacket/{recent["song_id"]}_{recent["difficulty"]}.jpg'
        if not os.path.exists(imgpath):
            imgpath = f'{assets_path}/jacket/{recent["song_id"]}.jpg'
        realptt = songinfo['rating'] / 10
        ptt = recent['rating']
        score = recent['score']
        shiny_pure = recent['shiny_perfect_count']
        pure = recent['perfect_count']
        far = recent['near_count']
        lost = recent['miss_count']
        username = get_['content']['account_info']['name']
        usrptt = int(get_['content']['account_info']['rating'])
        if usrptt == -1:
            usrptt = '--'
        else:
            usrptt = usrptt / 100
        time_played = datetime.fromtimestamp(recent['time_played'] / 1000)
        result = [Plain(msg.locale.t('arcaea.info.message.result', username=username, potential=potential, trackname=trackname, difficulty=difficulty, score=score, pure=pure, shiny_pure=shiny_pure, far=far, lost=lost, realptt=realptt, ptt=ptt, time_played=time_played.strftime("%Y-%m-%d %H:%M:%S")))]
        if os.path.exists(imgpath):
            result.append(Image(imgpath))
        else:
            asyncio.create_task(autofix_b30_song_background(recent["song_id"],
                                                            byd=False if recent["difficulty"] != 3 else True))
        return result
    elif get_['status'] in errcode:
        return Plain(f'{msg.locale.t('arcaea.message.failed.errcode')}{errcode[get_["status"]]}')
    else:
        return Plain(msg.locale.t('arcaea.message.failed') + get_)
