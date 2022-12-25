import asyncio
import os
import traceback
from datetime import datetime

from config import Config
from core.elements import Plain, Image
from core.logger import Logger
from core.utils import get_url
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
        return [Plain('查询失败：' + str(e))]
    except Exception:
        traceback.print_exc()
        return [Plain('查询失败。')]
    Logger.debug(get_)
    if get_["status"] == 0:
        recent = get_['content']["recent_score"]
        if len(recent) < 0:
            return [Plain('此用户无游玩记录。')]
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
        result = [Plain(f'{username} (Ptt: {usrptt})的最近游玩记录：\n'
                        f'{trackname} ({difficulty})\n'
                        f'Score: {score}\n'
                        f'Pure: {pure} ({shiny_pure})\n'
                        f'Far: {far}\n'
                        f'Lost: {lost}\n'
                        f'Potential: {realptt} -> {ptt}\n'
                        f'Time: {time_played.strftime("%Y-%m-%d %H:%M:%S")}(UTC+8)')]
        if os.path.exists(imgpath):
            result.append(Image(imgpath))
        else:
            asyncio.create_task(autofix_b30_song_background(recent["song_id"],
                                                            byd=False if recent["difficulty"] != 3 else True))
        return result
    elif get_['status'] in errcode:
        return Plain(f'查询失败：{errcode[get_["status"]]}')
    else:
        return Plain('查询失败。' + get_)
