from mirai import Mirai, Group, MessageChain, Member, Plain, At, Source, Image, Friend
qq = 2052142661 # 字段 qq 的值
authKey = '1145141919810' # 字段 authKey 的值
mirai_api_http_locate = 'localhost:11919/ws' # httpapi所在主机的地址端口,如果 setting.yml 文件里字段 "enableWebsocket" 的值为 "true" 则需要将 "/" 换成 "/ws", 否则将接收不到消息.

app = Mirai(f"mirai://{mirai_api_http_locate}?authKey={authKey}&qq={qq}",websocket=True)
@app.subroutine
async def ver(app: Mirai):
    await app.sendGroupMessage(657876815,[Plain('已开启检测游戏版本。')])
    from mcversion import mcversion
    import time
    import requests
    import json
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    verlist = mcversion()
    while True:
        version_manifest = requests.get(url)
        file = json.loads(version_manifest.text)
        release = file['latest']['release']
        snapshot = file['latest']['snapshot']
        if release in verlist:
            pass
        else:
            await app.sendGroupMessage(657876815,[Plain('启动器已更新'+file['latest']['release']+'正式版。')])
            addversion = open('mcversion.txt','a')
            addversion.write('\n'+release)
            addversion.close()
        if snapshot in verlist:
            pass
        else:
            await app.sendGroupMessage(657876815,[Plain('启动器已更新'+file['latest']['snapshot']+'快照。')])
            addversion = open('mcversion.txt','a')
            addversion.write('\n'+snapshot)
            addversion.close()
        print('没有')
        time.sleep(10)
if __name__ == "__main__":
    app.run()