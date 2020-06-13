import re
import requests
import json

def serverraw(address):
    matchObj = re.match(r'(.*):(.*).*', address, re.M|re.I)
    try:
        if matchObj:
            url = 'http://motd.wd-api.com/?ip='+matchObj.group(1)+'&port='+matchObj.group(2)+'&mode=info'
            motd = requests.get(url,timeout=10)
            file = json.loads(motd.text)
            try:
                if file['code'] == 200:
                    x = file['data']['description']['text']
                    if not x:
                        extra = file['data']['description']['extra']
                        return(str(extra)+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                    else:
                        return(x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                else:
                    return("连接服务器失败。")
            except Exception:
                try:
                    x = file['data']['description']
                    return(x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                except Exception:
                    return("发生错误：调用API时发生错误。")
        else:
            url = 'http://motd.wd-api.com/?ip='+address+'&port=25565&mode=info'
            motd = requests.get(url,timeout=10)
            file = json.loads(motd.text)
            try:
                if file['code'] == 200:
                    x = file['data']['description']['text']
                    if not x:
                        extra = file['data']['description']['extra']
                        return(str(extra)+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                    else:
                        return(x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                else:
                    return("连接服务器失败。")
            except Exception:
                try:
                    x = file['data']['description']
                    return(x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                except Exception:
                    return("发生错误：调用API时发生错误。")
    except Exception:
        return("发生错误：未知原因。")