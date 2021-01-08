import json
import re
import traceback

import aiohttp


async def server(address):
    matchObj = re.match(r'(.*):(.*)', address, re.M | re.I)
    servers = []

    try:
        if matchObj:
            serip = matchObj.group(1)
            port1 = matchObj.group(2)
            port2 = matchObj.group(2)
        else:
            serip = address
            port1 = '25565'
            port2 = '19132'

        try:
            url = 'http://motd.wd-api.com/java?ip=' + serip + '&port=' + port1 + '&mode=info'
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if req.status != 200:
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
                            servers.append(description['text'])
                        elif 'extra' in description:
                            extra = description['extra']
                            text = []
                            qwq = ''
                            for item in extra[:]:
                                text.append(item['text'])
                            servers.append(qwq.join(text))
                        else:
                            servers.append(description)

                    if 'players' in jejson:
                        onlinesplayer = f"在线玩家：{str(jejson['players']['online'])} / {str(jejson['players']['max'])}"
                        servers.append(onlinesplayer)
                    if 'version' in jejson:
                        versions = "游戏版本：" + file['data']['version']['name']
                        servers.append(versions)
                    servers.append(serip + ':' + port1)
                else:
                    print('获取JE服务器信息失败。')
            except Exception:
                traceback.print_exc()
                servers.append("[JE]\n发生错误：调用API时发生错误。")
        except Exception:
            print('获取JE服务器信息失败。')
            traceback.print_exc()
        try:
            beurl = 'http://motd.wd-api.com/bedrock?ip=' + serip + '&port=' + port2 + '&mode=info'
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if req.status != 200:
                        print(f"请求时发生错误：{req.status}")
                    else:
                        bemotd = await req.text()
                        bejson = json.loads(bemotd)
                        besplit = bejson['motd'].split(';')
                        motd_1 = besplit[1]
                        motd_2 = besplit[8]
                        player_count = besplit[5]
                        max_players = besplit[6]
                        edition = besplit[0]
                        version_name = besplit[4]
                        game_mode = besplit[9]
                        bemsg = '[BE]\n' +\
                        motd_1 + ' - ' + motd_2 +\
                        '\n在线玩家：' + player_count + '/' + max_players +\
                        '\n游戏版本：' + edition + version_name +\
                        '\n游戏模式：' + game_mode
                        servers.append(bemsg)

        except Exception:
            print('获取BE服务器信息失败。')
            traceback.print_exc()
        if str(servers) == '[]':
            return ('连接失败，没有检测到任何服务器。')
        else:
            awa = '\n'
            servers.append("[30秒后撤回本消息]")
            return re.sub(r'§\w', "", awa.join(servers))
    except Exception as e:
        return ("发生错误：" + str(e) + ".")
