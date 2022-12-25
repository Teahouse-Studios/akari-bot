import asyncio
import os
import uuid

import aiohttp
import ujson as json

from config import Config
from core.logger import Logger
from .drawb30img import drawb30
from .drawsongimg import dsimg
from .utils import autofix_b30_song_background, errcode

assets_path = os.path.abspath('./assets/arcaea')


async def getb30(usercode, official=False):
    headers = {"User-Agent": Config('botarcapi_agent')}
    d = 0
    last5rank = 0
    async with aiohttp.ClientSession() as session:
        url = Config("botarcapi_url")
        async with session.get(url + f"user/best30?usercode={usercode}&withsonginfo=True", headers=headers) as resp:
            if resp.status != 200:
                return {'text': f'获取失败：{str(resp.status)}[Ke:Image,path=https://http.cat/{str(resp.status)}.jpg]'}
            a = await resp.text()
            loadjson = json.loads(a)
            if loadjson["status"] == 0:
                b30 = round(loadjson["content"]["best30_avg"], 4)
                r10 = round(loadjson["content"]["recent10_avg"], 4)
                newdir = f'./cache/{str(uuid.uuid4())}'
                newdir = os.path.abspath(newdir)
                os.makedirs(newdir)
                tracknames = {}
                realptts = {}
                ptts = {}
                scores = {}
                last5list = ''
                run_lst = []
                songsinfo = {}
                for x in loadjson["content"]["best30_list"]:
                    songsinfo[x['song_id'] + str(x['difficulty'])] = loadjson["content"]["best30_songinfo"][d]
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
                        trackname = songsinfo[x['song_id'] + str(x['difficulty'])]['name_en']
                        tracknames[x['song_id'] + difficulty] = trackname + f' ({difficulty})'
                        imgpath = f'{assets_path}/b30background_img{"_official" if official else ""}/{x["song_id"]}_{str(x["difficulty"])}.jpg '
                        if not os.path.exists(imgpath):
                            imgpath = f'{assets_path}/b30background_img{"_official" if official else ""}/{x["song_id"]}.jpg'
                        realptt = songsinfo[x['song_id'] + str(x['difficulty'])]['rating']
                        realptts[x['song_id'] + difficulty] = realptt
                        ptt = x['rating']
                        ptts[x['song_id'] + difficulty] = ptt
                        score = x['score']
                        scores[x['song_id'] + difficulty] = score
                        if not os.path.exists(imgpath):
                            imgpath = f'{assets_path}/b30background_img{"_official" if official else ""}/random.jpg'
                            asyncio.create_task(autofix_b30_song_background(x['song_id'],
                                                                            byd=False if x['difficulty'] != 3 else True))
                        dsimg(os.path.abspath(imgpath), d, trackname, x['difficulty'], score, ptt, realptt,
                              x['perfect_count'], x['near_count'], x['miss_count'], x['time_played'], newdir)

                    run_lst.append(draw_jacket(x, d))
                await asyncio.gather(*run_lst)
                Logger.debug(tracknames)
                for last5 in loadjson["content"]["best30_list"][-5:]:
                    last5rank += 1
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
                    last5list += f'[{last5rank}] {trackname}\n[{last5rank}] {score} / {realptt / 10} -> {round(ptt, 4)}\n'
                Logger.debug(last5list)
                username = loadjson["content"]['account_info']['name']
                ptt = int(loadjson["content"]['account_info']['rating']) / 100
                character = loadjson["content"]['account_info']['character']
                filename = drawb30(username, b30, r10, ptt, character, newdir, official=official)
                filelist = os.listdir(newdir)
                for x in filelist:
                    os.remove(f'{newdir}/{x}')
                os.removedirs(newdir)
                return {'text': f'获取结果\nB30: {b30} | R10: {r10}\nB30倒5列表：\n{last5list}', 'file': filename}
            else:
                if loadjson['status'] in errcode:
                    return {'text': f'查询失败：{errcode[loadjson["status"]]}'}
                return {'text': '查询失败。' + a}
