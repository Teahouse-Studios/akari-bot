import os
import traceback

import ujson as json

from core.elements import FetchTarget, IntervalTrigger
from core.loader.decorator import schedule
from core.logger import Logger
from core.utils import get_url, PrivateAssets


def getfileversions(path):
    if not os.path.exists(path):
        a = open(path, 'a')
        a.close()
    w = open(path, 'r+')
    s = w.read().split('\n')
    w.close()
    return s


@schedule('mcv_rss', developers=['OasisAkari', 'Dianliang233'], trigger=IntervalTrigger(seconds=60))
async def mcv_rss(bot: FetchTarget):
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    try:
        version_file = os.path.abspath(f'{PrivateAssets.path}/mcversion.txt')
        verlist = getfileversions(version_file)
        file = json.loads(await get_url(url))
        release = file['latest']['release']
        snapshot = file['latest']['snapshot']
        if release not in verlist:
            Logger.info(f'huh, we find {release}.')
            await bot.post_message('mcv_rss', '启动器已更新' + file['latest']['release'] + '正式版。')
            addversion = open(version_file, 'a')
            addversion.write('\n' + release)
            addversion.close()
            verlist = getfileversions(version_file)
        if snapshot not in verlist:
            Logger.info(f'huh, we find {snapshot}.')
            await bot.post_message('mcv_rss', '启动器已更新' + file['latest']['snapshot'] + '快照。')
            addversion = open(version_file, 'a')
            addversion.write('\n' + snapshot)
            addversion.close()
    except Exception:
        traceback.print_exc()


@schedule('mcv_jira_rss', developers=['OasisAkari', 'Dianliang233'], trigger=IntervalTrigger(seconds=60))
async def mcv_jira_rss(bot: FetchTarget):
    try:
        version_file = os.path.abspath(f'{PrivateAssets.path}/mcjira_Java.txt')
        verlist = getfileversions(version_file)
        file = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/10400/versions'))
        releases = []
        for v in file:
            if not v['archived']:
                releases.append(v['name'])
        for release in releases:
            if release not in verlist:
                Logger.info(f'huh, we find {release}.')
                verlist.append(release)
                await bot.post_message('mcv_jira_rss',
                                                f'Jira已更新Java版 {release}。'
                                                f'\n（Jira上的信息仅作版本号预览用，不代表启动器已更新此版本）')
                addversion = open(version_file, 'a')
                addversion.write('\n' + release)
                addversion.close()
    except Exception:
        traceback.print_exc()


@schedule('mcbv_jira_rss', developers=['OasisAkari', 'Dianliang233'], trigger=IntervalTrigger(seconds=60))
async def mcbv_jira_rss(bot: FetchTarget):
    try:
        version_file = os.path.abspath(f'{PrivateAssets.path}/mcjira_Bedrock.txt')
        verlist = getfileversions(version_file)
        file = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/10200/versions'))
        releases = []
        for v in file:
            if not v['archived']:
                releases.append(v['name'])
        for release in releases:
            if release not in verlist:
                Logger.info(f'huh, we find {release}.')
                verlist.append(release)
                await bot.post_message('mcbv_jira_rss',
                                                f'Jira已更新基岩版 {release}。'
                                                f'\n（Jira上的信息仅作版本号预览用，不代表商城已更新此版本）')
                addversion = open(version_file, 'a')
                addversion.write('\n' + release)
                addversion.close()
    except Exception:
        traceback.print_exc()


@schedule('mcdv_jira_rss', developers=['OasisAkari', 'Dianliang233'], trigger=IntervalTrigger(seconds=60))
async def mcdv_jira_rss(bot: FetchTarget):
    try:
        version_file = os.path.abspath(f'{PrivateAssets.path}/mcjira_Minecraft Dungeons.txt')
        verlist = getfileversions(version_file)
        file = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/11901/versions'))
        releases = []
        for v in file:
            if not v['archived']:
                releases.append(v['name'])
        for release in releases:
            if release not in verlist:
                Logger.info(f'huh, we find {release}.')
                verlist.append(release)
                await bot.post_message('mcdv_jira_rss',
                                                f'Jira已更新Minecraft Dungeons {release}。'
                                                f'\n（Jira上的信息仅作版本号预览用，不代表启动器/商城已更新此版本）')
                addversion = open(version_file, 'a')
                addversion.write('\n' + release)
                addversion.close()
    except Exception:
        traceback.print_exc()
