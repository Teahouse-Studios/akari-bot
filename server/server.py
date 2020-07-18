import re
import requests
import json
import os, sys
from .be import main
async def server(address):
    matchObj = re.match(r'(.*):(.*).*', address, re.M|re.I)
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

        url = 'http://motd.wd-api.com/?ip='+serip+'&port='+port1+'&mode=info'
        motd = requests.get(url,timeout=10)
        file = json.loads(motd.text)
        try:
            if file['code'] == 200:
                x=re.sub(r'§\w',"",file['data']['description']['text'])
                if not x:
                    extra = file['data']['description']['extra']
                    text = []
                    qwq = ''
                    for item in extra[:]:
                        text.append(item['text'])
                    servers.append('[JE]\n'+qwq.join(text)+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                else:
                    servers.append('[JE]\n'+x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
            else:
                pass
        except Exception:
            try:
                x=re.sub(r'§\w',"",file['data']['description'])
                servers.append('[JE]\n'+x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
            except Exception as e:
                servers.append("[JE]\n发生错误：调用API时发生错误。")
        try:
            servers.append(await main(serip,port2))
        except Exception:
            pass
        if str(servers)=='[]':
            return('连接失败，没有检测到任何服务器。')
        else:
            awa = '\n'
            return(awa.join(servers))
    except Exception as e:      
        return("发生错误："+str(e)+".")