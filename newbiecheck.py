from datetime import datetime
import time
from UTC8 import UTC8
from pbc import main
import json
import requests
from mirai import Mirai, Group, MessageChain, Member, Plain, At, Source, Image, Friend
import traceback
qq = 2052142661 # 字段 qq 的值
authKey = '1145141919810' # 字段 authKey 的值
mirai_api_http_locate = 'localhost:11919/ws' # httpapi所在主机的地址端口,如果 setting.yml 文件里字段 "enableWebsocket" 的值为 "true" 则需要将 "/" 换成 "/ws", 否则将接收不到消息.

app = Mirai(f"mirai://{mirai_api_http_locate}?authKey={authKey}&qq={qq}",websocket=True)
@app.subroutine
async def newbie(app: Mirai):
    try:
        await app.sendGroupMessage(731397727,[Plain('开始检测新人。')])
        url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=logevents&letype=newusers&format=json'
        while True:
            try:
                q = requests.get(url, timeout=10)
                file = json.loads(q.text)
                qq = []
                for x in file['query']['logevents'][:]:
                    qq.append(x['title'])
                    print('!' + x['title'])
                while True:
                    c = 'f'
                    try:
                        qqq = requests.get(url, timeout=10)
                        qqqq = json.loads(qqq.text)
                        for xz in qqqq['query']['logevents'][:]:
                            if xz['title'] in qq:
                                pass
                            else:
                                s = await main(UTC8(xz['timestamp']) + '新增新人：' + xz['title'])
                                if s[0].find("<吃掉了>")!=-1 or s[0].find("<全部吃掉了>")!=-1:
                                    await app.sendGroupMessage(731397727,message=s[0]+'\n检测到外来信息介入，请前往日志查看所有消息。Special:日志?type=newusers')
                                else:
                                    await app.sendGroupMessage(731397727, message=s[0])
                                print(s)
                                c = 't'
                    except Exception:
                        pass
                    if c == 't':
                        break
                    else:
                        print('nope')
                        time.sleep(10)
                        pass
                time.sleep(5)
            except Exception as e:
                traceback.print_exc()
                print('xxx' + str(e))
    except Exception as e:
        traceback.print_exc()
        print(str(e)) 
if __name__ == "__main__":
    app.run()