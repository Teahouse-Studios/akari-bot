import asyncio
import time
import traceback

from graia.application import GraiaMiraiApplication, Session
from graia.application.message.chain import MessageChain
from graia.application.message.elements.internal import Plain
from graia.broadcast import Broadcast

from modules.UTC8 import UTC8
from modules.pbc import pbc1

loop = asyncio.get_event_loop()

bcc = Broadcast(loop=loop, debug_flag=True)
app = GraiaMiraiApplication(
    broadcast=bcc,
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
async def newbie(app: GraiaMiraiApplication):
    try:
        await app.sendGroupMessage(731397727, MessageChain.create([Plain('开始检测新人。')]).asSendable())
        url = 'https://minecraft-zh.gamepedia.com/api.php?action=query&list=logevents&letype=newusers&format=json'
        while True:
            try:
                file = await get_data(url, 'json')
                qq = []
                for x in file['query']['logevents'][:]:
                    qq.append(x['title'])
                    print('!' + x['title'])
                while True:
                    c = 'f'
                    try:
                        qqqq = await get_data(url, 'json')
                        for xz in qqqq['query']['logevents'][:]:
                            if xz['title'] in qq:
                                pass
                            else:
                                s = await pbc1(UTC8(xz['timestamp'], 'onlytime') + '新增新人：' + xz['title'])
                                print(s)
                                if s[0].find("<吃掉了>") != -1 or s[0].find("<全部吃掉了>") != -1:
                                    await app.sendGroupMessage(731397727, MessageChain.create([Plain(s[
                                                                                                         0] + '\n检测到外来信息介入，请前往日志查看所有消息。Special:日志?type=newusers')]).asSendable())
                                else:
                                    await app.sendGroupMessage(731397727,
                                                               MessageChain.create([Plain(s[0])]).asSendable())
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
    app.launch_blocking()
