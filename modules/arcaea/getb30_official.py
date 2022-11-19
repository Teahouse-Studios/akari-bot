"""
This service utilizes API functionality provided by and with permission from lowiro. It is not affiliated with or endorsed by lowiro.
"""
import asyncio
import os
import traceback
import uuid

from config import Config
from core.logger import Logger
from core.utils import get_url
from .drawb30img import drawb30
from .drawsongimg import dsimg
from .utils import autofix_b30_song_background

assets_path = os.path.abspath('./assets/arcaea')

apiurl = Config('arcapi_official_url')
headers = {'Authorization': Config('arcapi_official_token')}
headers_botarcapi = {"User-Agent": Config('botarcapi_agent')}
botarcapi_url = Config('botarcapi_url')


async def getb30_official(usercode):
    try:
        getuserinfo_json = await get_url(f'{apiurl}user/{usercode}', headers=headers, status_code=200, fmt='json')
        getb30_json = await get_url(f'{apiurl}user/{usercode}/best', headers=headers, status_code=200, fmt='json')
    except Exception:
        traceback.print_exc()
        return {'text': f'获取失败。'}
    getuserinfo = getuserinfo_json['data']
    username = getuserinfo['display_name']
    potential = getuserinfo['potential']
    if potential is not None:
        potential = int(potential) / 100
    else:
        potential = '--'
    getb30 = getb30_json['data']
    b30potential = []
    for x in getb30:
        b30potential.append(x['potential_value'])
    b30_avg = round(sum(b30potential) / len(b30potential), 4)
    if potential is not None and isinstance(potential, (int, float)):
        r10_avg = round((potential * 40 - b30_avg * 30) / 10, 4)
    else:
        r10_avg = '???'
    songsinfo = {}
    getinfos = []
    for x in getb30:
        async def get_songinfo(songid):
            try:
                get_songinfo_from_botarcapi = await get_url(f'{botarcapi_url}song/info?songid={songid}',
                                                            headers=headers_botarcapi, status_code=200, fmt='json')
                songsinfo[songid] = get_songinfo_from_botarcapi['content']
            except Exception:
                traceback.print_exc()

        getinfos.append(get_songinfo(x['song_id']))
    await asyncio.gather(*getinfos)
    newdir = f'./cache/{str(uuid.uuid4())}'
    newdir = os.path.abspath(newdir)
    os.makedirs(newdir)
    d = 0
    tracknames = {}
    ptts = {}
    realptts = {}
    scores = {}
    run_lst = []
    for x in getb30:
        d = d + 1

        async def draw_jacket(x, d):
            difficulty = '???'
            if x['difficulty'] == 0:
                difficulty = 'PST'
            elif x['difficulty'] == 1:
                difficulty = 'PRS'
            elif x['difficulty'] == 2:
                difficulty = 'FTR'
            elif x['difficulty'] == 3:
                difficulty = 'BYD'
            songinfo = songsinfo.get(x['song_id'], {})
            trackname = x['song_id']
            realptt = False
            if songinfo:
                trackname = songinfo['difficulties'][x['difficulty']]['name_en']
                realptt = songinfo['difficulties'][x['difficulty']]['rating']
                realptts[x['song_id'] + difficulty] = realptt
            tracknames[x['song_id'] + difficulty] = trackname + f' ({difficulty})'
            imgpath = f'{assets_path}/b30background_img_official/{x["song_id"]}_{str(x["difficulty"])}.jpg'
            if not os.path.exists(imgpath):
                imgpath = f'{assets_path}/b30background_img_official/{x["song_id"]}.jpg'
            score = x['score']
            if not realptt:
                realptt = x['potential_value']
                if score >= 10000000:
                    realptt -= 2
                elif score >= 9800000:
                    realptt -= 1 + (score - 9800000) / 200000
                elif score <= 9500000:
                    realptt -= (score - 9500000) / 300000
                realptt = round(realptt, 1) * 10
                realptts[x['song_id'] + difficulty] = realptt
            ptt = x['potential_value']
            ptts[x['song_id'] + difficulty] = ptt
            scores[x['song_id'] + difficulty] = score
            if not os.path.exists(imgpath):
                imgpath = f'{assets_path}/b30background_img_official/random.jpg'
                asyncio.create_task(autofix_b30_song_background(x['song_id'],
                                                                byd=False if x['difficulty'] != 3 else True))
            dsimg(os.path.abspath(imgpath), d, trackname, x['difficulty'], score, ptt, realptt,
                  x['pure_count'], x['far_count'], x['lost_count'], x['time_played'], newdir)

        run_lst.append(draw_jacket(x, d))
    await asyncio.gather(*run_lst)
    last5rank = 0
    last5list = ''
    for last5 in getb30[-5:]:
        last5rank += 1
        difficulty = '???'
        if last5['difficulty'] == 0:
            difficulty = 'PST'
        if last5['difficulty'] == 1:
            difficulty = 'PRS'
        if last5['difficulty'] == 2:
            difficulty = 'FTR'
        if last5['difficulty'] == 3:
            difficulty = 'BYD'
        trackname = tracknames[last5['song_id'] + difficulty]
        realptt = realptts[last5['song_id'] + difficulty]
        ptt = ptts[last5['song_id'] + difficulty]
        score = scores[last5['song_id'] + difficulty]
        last5list += f'[{last5rank}] {trackname}\n' \
                     f'[{last5rank}] {score} / {realptt / 10} -> {round(ptt, 4)}\n'
    Logger.debug(last5list)
    filename = drawb30(username, b30_avg, r10_avg, potential, 0, newdir, official=True)
    filelist = os.listdir(newdir)
    for x in filelist:
        os.remove(f'{newdir}/{x}')
    os.removedirs(newdir)
    return {'text': f'获取结果\nB30: {b30_avg} | R10: {r10_avg}\nB30倒5列表：\n{last5list}', 'file': filename}
