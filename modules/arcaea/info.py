import asyncio
import os
import traceback
from datetime import datetime

from config import Config
from core.builtins import Plain, Image
from core.logger import Logger
from core.utils.http import get_url
from modules.arcaea.utils import autofix_b30_song_background

assets_path = os.path.abspath('./assets/arcaea')
api_url = Config("botarcapi_url")
headers = {"Authorization": f'Bearer {Config("botarcapi_token")}'}


async def get_info(msg, usercode):
    try:
        get_ = await get_url(f"{api_url}/user/info?user_code={usercode}&recent=1&with_song_info=True",
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
            return [Plain(msg.locale.t('arcaea.message.info.result.none'))]
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
        songinfo = get_['content']['song_info'][0]
        trackname = songinfo['name_en']
        imgpath = f'{assets_path}/jacket/{recent["song_id"]}_{recent["difficulty"]}.jpg'
        if not os.path.exists(imgpath):
            imgpath = f'{assets_path}/jacket/{recent["song_id"]}.jpg'
        realptt = songinfo['rating'] / 10
        score = recent['score']
        ptt = realptt
        if score >= 10000000:
            ptt += 2
        elif score >= 9800000:
            ptt += 1 + (score - 9800000) / 200000
        else:
            ptt += (score - 9500000) / 300000
        username = get_['content']['account_info']['name']
        usrptt = int(get_['content']['account_info']['rating'])
        if usrptt == -1:
            usrptt = '--'
        else:
            usrptt = usrptt / 100
        time_played = datetime.fromtimestamp(recent['time_played'] / 1000)
        result = [
            Plain(
                msg.locale.t(
                    'arcaea.message.info.result',
                    username=username,
                    potential=usrptt,
                    trackname=trackname,
                    difficulty=difficulty,
                    score=score,
                    realptt=realptt,
                    ptt=ptt,
                    time_played=time_played.strftime("%Y-%m-%d %H:%M:%S")))]
        if os.path.exists(imgpath):
            result.append(Image(imgpath))
        else:
            asyncio.create_task(autofix_b30_song_background(recent["song_id"],
                                                            byd=False if recent["difficulty"] != 3 else True))
        return result

    else:
        errcode_string = f"arcaea.errcode.{get_['status']}"
        if locale := msg.locale.t(errcode_string) != errcode_string:
            return Plain(f'{msg.locale.t("arcaea.message.failed.errcode")}{locale}')
        return Plain(msg.locale.t('arcaea.message.failed') + get_)
