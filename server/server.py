import re
import requests
import json
import os, sys

def server(address):
    matchObj = re.match(r'(.*):(.*).*', address, re.M|re.I)
    try:
        if matchObj:
            url = 'http://motd.wd-api.com/?ip='+matchObj.group(1)+'&port='+matchObj.group(2)+'&mode=info'
            motd = requests.get(url,timeout=10)
            file = json.loads(motd.text)
            try:
                if file['code'] == 200:
                    x=re.sub(r'§\w',"",file['data']['description']['text'])
                    if not x:
                        extra = file['data']['description']['extra']
                        for item in extra[:]:
                            text = item['text']
                            y = open('cache_text.txt',mode='a',encoding='utf-8')
                            y.write(text)
                            y.close()
                        z = open('cache_text.txt',mode='r',encoding='utf-8')
                        return(z.read()+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                        z.close()
                        os.remove('cache_text.txt')
                    else:
                        return(x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                else:
                    return("连接服务器失败。")
            except Exception:
                try:
                    x=re.sub(r'§\w',"",file['data']['description'])
                    return(x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                except Exception:
                    return("发生错误：调用API时发生错误。")
        else:
            url = 'http://motd.wd-api.com/?ip='+address+'&port=25565&mode=info'
            motd = requests.get(url,timeout=10)
            file = json.loads(motd.text)
            try:
                if file['code'] == 200:
                    x=re.sub(r'§\w',"",file['data']['description']['text'])
                    if not x:
                        extra = file['data']['description']['extra']
                        for item in extra[:]:
                            text = item['text']
                            y = open('cache_text.txt',mode='a',encoding='utf-8')
                            y.write(text)
                            y.close()
                        z = open('cache_text.txt',mode='r',encoding='utf-8')
                        return(z.read()+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                        z.close()
                        os.remove('cache_text.txt')
                    else:
                        return(x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                else:
                    return("连接服务器失败。")
            except Exception:
                try:
                    x=re.sub(r'§\w',"",file['data']['description'])
                    return(x+"\n"+"在线玩家："+str(file['data']['players']['online'])+"/"+str(file['data']['players']['max'])+"\n"+"游戏版本："+file['data']['version']['name'])
                except Exception:
                    return("发生错误：调用API时发生错误。")
    except Exception as e:      
        return("发生错误："+str(e)+".")