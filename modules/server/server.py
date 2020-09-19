import json
import re

import aiohttp

from .be import main


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
            url = 'http://motd.wd-api.com/?ip=' + serip + '&port=' + port1 + '&mode=info'
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    if req.status != 200:
                        print(f"请求时发生错误：{req.status}")
                    else:
                        motd = await req.text()
            file = json.loads(motd)
            try:
                if file['code'] == 200:
                    x = re.sub(r'§\w', "", file['data']['description']['text'])
                    if not x:
                        extra = file['data']['description']['extra']
                        text = []
                        qwq = ''
                        for item in extra[:]:
                            text.append(item['text'])
                        servers.append('[JE]\n' + qwq.join(text) + "\n" + "在线玩家：" + str(
                            file['data']['players']['online']) + "/" + str(
                            file['data']['players']['max']) + "\n" + "游戏版本：" + file['data']['version']['name'])
                    else:
                        servers.append(
                            '[JE]\n' + x + "\n" + "在线玩家：" + str(file['data']['players']['online']) + "/" + str(
                                file['data']['players']['max']) + "\n" + "游戏版本：" + file['data']['version']['name'])
                else:
                    print('获取JE服务器信息失败。')
            except Exception:
                try:
                    x = re.sub(r'§\w', "", file['data']['description'])
                    servers.append('[JE]\n' + x + "\n" + "在线玩家：" + str(file['data']['players']['online']) + "/" + str(
                        file['data']['players']['max']) + "\n" + "游戏版本：" + file['data']['version']['name'])
                except Exception as e:
                    print('获取JE服务器信息失败。' + str(e))
                    servers.append("[JE]\n发生错误：调用API时发生错误。")
        except Exception as e:
            print('获取JE服务器信息失败。' + str(e))
        try:
            BE = await main(serip, port2)
            BER = re.sub(r'§\w', "", BE)
            servers.append(BER)
        except Exception as e:
            print('获取BE服务器信息失败。' + str(e))
        if str(servers) == '[]':
            return ('连接失败，没有检测到任何服务器。')
        else:
            awa = '\n'
            servers.append("[30秒后撤回本消息]")
            return (awa.join(servers))
    except Exception as e:
        return ("发生错误：" + str(e) + ".")
