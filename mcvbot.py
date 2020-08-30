import asyncio
import traceback

from graia.application import GraiaMiraiApplication, Session
from graia.application.message.chain import MessageChain
from graia.application.message.elements.internal import Plain
from graia.broadcast import Broadcast

loop = asyncio.get_event_loop()

bcc = Broadcast(loop=loop, debug_flag=True)
app = GraiaMiraiApplication(
    broadcast=bcc,
    enable_chat_log=False,
    connect_info=Session(
        host="http://localhost:11919",  # 填入 httpapi 服务运行的地址
        authKey='1145141919810',  # 填入 authKey
        account=2052142661,  # 你的机器人的 qq 号
        websocket=True  # Graia 已经可以根据所配置的消息接收的方式来保证消息接收部分的正常运作.
    )
)
import aiohttp
async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")

@bcc.receiver("ApplicationLaunched")
async def ver(app: GraiaMiraiApplication):
    from modules.mcvrss import mcvrss
    for qqgroup in mcvrss():
        try:
            await app.sendGroupMessage(int(qqgroup), MessageChain.create([Plain('已开启检测游戏版本。')]).asSendable())
        except Exception as e:
            traceback.print_exc()
            print(str(e))

    from mcversion import mcversion
    import time
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    while True:
        try:
            verlist = mcversion()
            file = await get_data(url,'json')
            release = file['latest']['release']
            snapshot = file['latest']['snapshot']
            if release in verlist:
                pass
            else:
                for qqgroup in mcvrss():
                    try:
                        await app.sendGroupMessage(int(qqgroup), MessageChain.create([Plain('启动器已更新' + file['latest']['release'] + '正式版。')]).asSendable())
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
                        await app.sendGroupMessage(int(qqgroup), MessageChain.create([Plain('启动器已更新' + file['latest']['snapshot'] + '快照。')]).asSendable())
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
    app.launch_blocking()
