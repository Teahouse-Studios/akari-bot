import json
import re
import traceback

import aiohttp


async def server(address, raw=False, showplayer=False, mode='j'):
    matchObj = re.match(r'(.*):(.*)', address, re.M | re.I)
    servers = []

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
        print(matchserip.group(1), matchserip.group(2),
              matchserip.group(3), matchserip.group(4))
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
            url = 'http://motd.wd-api.com/java?ip=' + serip + '&port=' + port1
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if req.status != 200:
                        print(await req.text())
                        print(f"请求时发生错误：{req.status}")
                    else:
                        motd = await req.text()
                        file = json.loads(motd)
                        try:
                            if file['code'] == 200:
                                servers.append('[JE]')
                                jejson = file['data']
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
                                        for x in jejson['players']['sample']:
                                            playerlist.append(x['name'])
                                        servers.append('当前在线玩家：\n' + '\n'.join(playerlist))
                                if 'version' in jejson:
                                    versions = "游戏版本：" + file['data']['version']['name']
                                    servers.append(versions)
                                servers.append(serip + ':' + port1)
                            else:
                                servers.append('获取JE服务器信息失败。')
                        except Exception:
                            traceback.print_exc()
                            servers.append("[JE]\n发生错误：调用API时发生错误。")
        except Exception:
            servers.append('获取JE服务器信息失败。')
            traceback.print_exc()
        awa = '\n'
        servers.append("[120秒后撤回本消息]")
        print(servers)
        if raw:
            return awa.join(servers)
        return re.sub(r'§\w', "", awa.join(servers))
    if mode == 'b':
        try:
            beurl = 'http://motd.wd-api.com/bedrock?ip=' + serip + '&port=' + port2
            async with aiohttp.ClientSession() as session2:
                async with session2.get(beurl, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if req.status != 200:
                        print(await req.text())
                        servers.append(f'获取BE服务器信息失败：{req.status}')
                    else:
                        bemotd = await req.text()
                        bejson = json.loads(bemotd)
                        print(bejson)
                        edition, motd_1, protocol, version_name, player_count, max_players, unique_id, motd_2, \
                        game_mode, game_mode_num = bejson['motd'].split(';')
                        bemsg = '[BE]\n' + \
                                motd_1 + ' - ' + motd_2 + \
                                '\n在线玩家：' + player_count + '/' + max_players + \
                                '\n游戏版本：' + edition + version_name + \
                                '\n游戏模式：' + game_mode
                        servers.append(bemsg)

        except Exception:
            servers.append('获取BE服务器信息失败。')
            traceback.print_exc()
        awa = '\n'
        servers.append("[120秒后撤回本消息]")
        print(servers)
        if raw:
            return awa.join(servers)
        return re.sub(r'§\w', "", awa.join(servers))
