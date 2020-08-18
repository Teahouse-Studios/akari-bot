from mirai import Mirai, Plain

qq = 2052142661  # 字段 qq 的值
authKey = '1145141919810'  # 字段 authKey 的值
mirai_api_http_locate = 'localhost:11919/ws'  # httpapi所在主机的地址端口,如果 setting.yml 文件里字段 "enableWebsocket" 的值为 "true" 则需要将 "/" 换成 "/ws", 否则将接收不到消息.

app = Mirai(f"mirai://{mirai_api_http_locate}?authKey={authKey}&qq={qq}", websocket=True)


@app.subroutine
async def ver(app: Mirai):
    from plugins.mcvrss import mcvrss
    for qqgroup in mcvrss():
        try:
            await app.sendGroupMessage(int(qqgroup), [Plain('已开启检测游戏版本。')])
        except Exception as e:
            print(str(e))

    from mcversion import mcversion
    import time
    import requests
    import json
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    while True:
        try:
            verlist = mcversion()
            version_manifest = requests.get(url)
            file = json.loads(version_manifest.text)
            release = file['latest']['release']
            snapshot = file['latest']['snapshot']
            if release in verlist:
                pass
            else:
                for qqgroup in mcvrss():
                    try:
                        await app.sendGroupMessage(int(qqgroup), [Plain('启动器已更新' + file['latest']['release'] + '正式版。')])
                    except Exception as e:
                        print(str(e))
                addversion = open('mcversion.txt', 'a')
                addversion.write('\n' + release)
                addversion.close()
            if snapshot in verlist:
                pass
            else:
                for qqgroup in mcvrss():
                    try:
                        await app.sendGroupMessage(int(qqgroup), [Plain('启动器已更新' + file['latest']['snapshot'] + '快照。')])
                    except Exception as e:
                        print(str(e))
                addversion = open('mcversion.txt', 'a')
                addversion.write('\n' + snapshot)
                addversion.close()
            print('ping')
            time.sleep(10)
        except Exception as e:
            print(str(e))
            time.sleep(5)


if __name__ == "__main__":
    app.run()
