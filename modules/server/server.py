import re
import traceback

import aiohttp
import ujson as json

from core.elements import ErrorMessage
from core.logger import Logger


async def server(address, raw=False, showplayer=False, mode='j'):
    matchObj = re.match(r'(.*)[\s:]~server 111.9.62.18:4104(.*)', address, re.M | re.I)
    servers = []
    n = '\n'

    if matchObj:
        serip = matchObj.group(1)
        port1 = matchObj.group(2)
        port2 = matchObj.group(2)
    else:
        serip = address
        port1 = '25565'
        port2 = '19132'
    matchserip = re.match(r'(.*?)\.(.*?)\.(.*?)\.(.*?)', serip)
    if matchserip:
        try:
            if matchserip.group(1) == '192':
                if matchserip.group(2) == '168':
                    return '¿'
            if matchserip.group(1) == '172':
                if 16 <= int(matchserip.group(2)) <= 31:
                    return '¿'
            if matchserip.group(1) == '10':
                if 0 <= int(matchserip.group(2)) <= 255:
                    return '¿'
            if matchserip.group(1) == '0':
                if matchserip.group(2) == '0':
                    if matchserip.group(3) == '0':
                        return '¿'
        except:
            traceback.print_exc()
    if mode == 'j':
        try:
            url = 'http://motd.wd-api.com/v1/java?host=' + serip + '&port=' + port1
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if req.status != 200:
                        print(await req.text())
                    else:
                        jejson = json.loads(await req.text())
                        try:
                            servers.append('[JE]')
                            if 'description' in jejson:
                                description = jejson['description']
                                if 'text' in description:
                                    servers.append(str(description['text']))
                                elif 'extra' in description:
                                    extra = description['extra']
                                    text = []
                                    qwq = ''
                                    for item in extra[:]:
                                        text.append(str(item['text']))
                                    servers.append(qwq.join(text))
                                else:
                                    servers.append(str(description))

                            if 'players' in jejson:
                                onlinesplayer = f"在线玩家：{str(jejson['players']['online'])} / {str(jejson['players']['max'])}"
                                servers.append(onlinesplayer)
                                if showplayer:
                                    playerlist = []
                                    if 'sample' in jejson['players']:
                                        for x in jejson['players']['sample']:
                                            playerlist.append(x['name'])
                                        servers.append('当前在线玩家：\n' + '\n'.join(playerlist))
                                    else:
                                        if jejson['players']['online'] == 0:
                                            servers.append('当前在线玩家：\n无')
                            if 'version' in jejson:
                                versions = "游戏版本：" + jejson['version']['name']
                                servers.append(versions)
                            servers.append(serip + ':' + port1)
                        except Exception:
                            traceback.print_exc()
                            servers.append(str(ErrorMessage("JE查询调用API时发生错误。")))
        except Exception:
            traceback.print_exc()
        if raw:
            return n.join(servers)
        return re.sub(r'§\w', "", n.join(servers))
    if mode == 'b':
        try:
            beurl = 'http://motd.wd-api.com/v1/bedrock?host=' + serip + '&port=' + port2
            print(beurl)
            async with aiohttp.ClientSession() as session2:
                async with session2.get(beurl, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if req.status != 200:
                        Logger.debug(await req.text())
                    else:
                        bemotd = await req.text()
                        bejson = json.loads(bemotd)
                        unpack_data = bejson['data'].split(';')
                        motd_1 = unpack_data[1]
                        motd_2 = unpack_data[7]
                        player_count = unpack_data[4]
                        max_players = unpack_data[5]
                        edition = unpack_data[0]
                        version_name = unpack_data[3]
                        game_mode = unpack_data[8]
                        bemsg = '[BE]\n' + \
                                motd_1 + ' - ' + motd_2 + \
                                '\n在线玩家：' + player_count + '/' + max_players + \
                                '\n游戏版本：' + edition + version_name + \
                                '\n游戏模式：' + game_mode
                        servers.append(bemsg)
                        servers.append(serip + ':' + port2)

        except Exception:
            traceback.print_exc()
        if raw:
            return n.join(servers)
        return re.sub(r'§\w', "", n.join(servers))
