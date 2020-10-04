import asyncio
import traceback

import aiohttp
from graia.application import MessageChain
from graia.application.message.elements.internal import Plain

from modules.UTC8 import UTC8
from modules.pbc import pbc1


async def get_data(url: str, fmt: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            if hasattr(req, fmt):
                return await getattr(req, fmt)()
            else:
                raise ValueError(f"NoSuchMethod: {fmt}")


async def newbie(app):
    print('subbot newbie launched')
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
                            c = 't'
                except Exception:
                    pass
                if c == 't':
                    break
                else:
                    await asyncio.sleep(10)
            await asyncio.sleep(5)
        except Exception:
            traceback.print_exc()


async def ver(app):
    from modules.mcvrss import mcvrss
    from modules.mcversion import mcversion
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    print('subbot ver launched')
    while True:
        try:
            verlist = mcversion()
            file = await get_data(url, 'json')
            release = file['latest']['release']
            snapshot = file['latest']['snapshot']
            if release in verlist:
                pass
            else:
                for qqgroup in mcvrss():
                    try:
                        await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                            [Plain('启动器已更新' + file['latest']['release'] + '正式版。')]).asSendable())
                    except Exception:
                        traceback.print_exc()
                addversion = open('./assets/mcversion.txt', 'a')
                addversion.write('\n' + release)
                addversion.close()
            if snapshot in verlist:
                pass
            else:
                for qqgroup in mcvrss():
                    try:
                        await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                            [Plain('启动器已更新' + file['latest']['snapshot'] + '快照。')]).asSendable())
                    except Exception:
                        traceback.print_exc()
                addversion = open('./assets/mcversion.txt', 'a')
                addversion.write('\n' + snapshot)
                addversion.close()
            await asyncio.sleep(10)
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(5)