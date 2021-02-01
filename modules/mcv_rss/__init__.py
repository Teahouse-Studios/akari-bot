import asyncio
import traceback
from os.path import abspath

from graia.application import MessageChain
from graia.application.message.elements.internal import Plain

from database import check_enable_modules_all
from modules.mcv.mcv import get_data


def mcversion():
    w = open(abspath('./assets/mcversion.txt'), 'r+')
    s = w.read().split('\n')
    w.close()
    return s


def mcversion_jira():
    w = open(abspath('./assets/mcversion_jira.txt'), 'r+')
    s = w.read().split('\n')
    w.close()
    return s


async def mcv_rss(app):
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    print('subbot ver launched')
    while True:
        try:
            verlist = mcversion()
            file = await get_data(url, 'json')
            release = file['latest']['release']
            snapshot = file['latest']['snapshot']
            if release not in verlist:
                print(release)
                for qqgroup in check_enable_modules_all('group_permission', 'mcv_rss'):
                    try:
                        await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                            [Plain('启动器已更新' + file['latest']['release'] + '正式版。')]))
                        await asyncio.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
                addversion = open('./assets/mcversion.txt', 'a')
                addversion.write('\n' + release)
                addversion.close()
                verlist = mcversion()
            if snapshot not in verlist:
                print(snapshot)
                for qqgroup in check_enable_modules_all('group_permission', 'mcv_rss'):
                    try:
                        await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                            [Plain('启动器已更新' + file['latest']['snapshot'] + '快照。')]))
                        await asyncio.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
                addversion = open('./assets/mcversion.txt', 'a')
                addversion.write('\n' + snapshot)
                addversion.close()
            await asyncio.sleep(10)
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(5)


async def mcv_jira_rss(app):
    url = 'https://bugs.mojang.com/rest/api/2/project/10400/versions'
    print('subbot jira launched')
    while True:
        try:
            verlist = mcversion_jira()
            file = await get_data(url, 'json')
            release = []
            for v in file:
                if not v['archived']:
                    release.append(v['name'])
            for x in release:
                if x not in verlist:
                    print(x)
                    for qqgroup in check_enable_modules_all('group_permission', 'mcv_jira_rss'):
                        try:
                            await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                                [Plain(f'Jira已更新{x}。\n（Jira上的信息仅作版本号预览用，不代表启动器已更新此版本）')]))
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                    addversion = open('./assets/mcversion_jira.txt', 'a')
                    addversion.write('\n' + x)
                    addversion.close()
            await asyncio.sleep(10)
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(5)


rss = {'mcv_rss': mcv_rss, 'mcv_jira_rss': mcv_jira_rss}
options = ['mcv_rss', 'mcv_jira_rss']
help = {'mcv_rss': {'module': '订阅Minecraft Java版游戏版本检测。（仅群聊）'},
        'mcv_jira_rss': {'module': '订阅Minecraft Java版游戏版本检测（Jira记录，仅作预览用）。（仅群聊）'}}
