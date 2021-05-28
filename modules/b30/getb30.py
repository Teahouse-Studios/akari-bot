import json
import os
import uuid

import aiohttp

from .drawb30img import drawb30
from .drawsongimg import dsimg


async def getb30(usercode):
    headers = {"User-Agent": "OasisAkari/*"}
    d = 0
    last5rank = 0
    async with aiohttp.ClientSession() as session:
        url = "http://127.0.0.1:2333/v2/"
        async with session.get(url + "userbest30?usercode=" + usercode, headers=headers) as resp:
            a = await resp.text()
            loadjson = json.loads(a)
            if loadjson["status"] == 0:
                b30 = loadjson["content"]["best30_avg"]
                r10 = loadjson["content"]["recent10_avg"]
                newdir = f'./cache/{str(uuid.uuid4())}'
                newdir = os.path.abspath(newdir)
                os.makedirs(newdir)
                tracknames = {}
                realptts = {}
                ptts = {}
                scores = {}
                last5list = ''
                for x in loadjson["content"]["best30_list"]:
                    d = d + 1
                    async with session.get(url + "songinfo?songname=" + x['song_id'], headers=headers) as name:
                        b = await name.text()
                        loadname = json.loads(b)
                        if x['difficulty'] == 0:
                            difficulty = 'PST'
                        if x['difficulty'] == 1:
                            difficulty = 'PRS'
                        if x['difficulty'] == 2:
                            difficulty = 'FTR'
                        if x['difficulty'] == 3:
                            difficulty = 'BYD'
                        trackname = loadname['content']['title_localized']['en']
                        tracknames[x['song_id'] + difficulty] = trackname + f' ({difficulty})'
                        imgpath = f'./assets/arcaea/songimg/{x["song_id"]}.jpg'
                        realptt = loadname['content']['difficulties'][x['difficulty']]['ratingReal']
                        realptts[x['song_id'] + difficulty] = realptt
                        ptt = x['rating']
                        ptts[x['song_id'] + difficulty] = ptt
                        score = x['score']
                        scores[x['song_id'] + difficulty] = score
                        if not os.path.exists(imgpath):
                            imgpath = f'./assets/arcaea/songimg/random.jpg'
                        dsimg(os.path.abspath(imgpath), d, trackname, x['difficulty'], score, ptt, realptt,
                              x['perfect_count'], x['near_count'], x['miss_count'], x['time_played'], newdir)
                print(tracknames)
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
                    last5list += f'[{last5rank}] {trackname}\n[{last5rank}] {score} / {realptt} -> {round(ptt, 4)}\n'
                print(last5list)
                async with session.get(url + "userinfo?usercode=" + usercode, headers=headers) as resp:
                    userinfo = await resp.text()
                    loaduserjson = json.loads(userinfo)
                    username = loaduserjson['content']['name']
                    ptt = int(loaduserjson['content']['rating']) / 100
                    character = loaduserjson['content']['character']
                    filename = drawb30(username, b30, r10, ptt, character, newdir)
                    filelist = os.listdir(newdir)
                    for x in filelist:
                        os.remove(f'{newdir}/{x}')
                    os.removedirs(newdir)
                    return {'text': f'获取结果\nB30: {b30} | R10: {r10}\nB30倒5列表：\n{last5list}', 'file': filename}
            elif loadjson["status"] == -1:
                return {'text': '[-1] 非法的好友码。'}
            elif loadjson["status"] == -4:
                return {'text': '[-4] 查询失败。'}
            elif loadjson["status"] == -6:
                return {'text': '[-6] 没有游玩记录。'}
            else:
                return {'text': '查询失败。' + a}
