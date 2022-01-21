import os
import traceback

import ujson as json

from core.component import on_schedule
from core.elements import FetchTarget, IntervalTrigger, PrivateAssets
from core.logger import Logger
from core.utils import get_url


def getfileversions(path):
    if not os.path.exists(path):
        a = open(path, 'a', encoding='utf-8')
        a.close()
    w = open(path, 'r+', encoding='utf-8')
    s = w.read().split('\n')
    w.close()
    return s


@on_schedule('mcv_rss',
             developers=['OasisAkari', 'Dianliang233'],
             recommend_modules=['mcv_jira_rss', 'mcbv_jira_rss', 'mcdv_jira_rss'],
             trigger=IntervalTrigger(seconds=60),
             desc='开启后当Minecraft启动器更新时将会自动推送消息。', alias='mcvrss')
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
            addversion = open(version_file, 'a', encoding='utf-8')
            addversion.write('\n' + release)
            addversion.close()
            verlist = getfileversions(version_file)
        if snapshot not in verlist:
            Logger.info(f'huh, we find {snapshot}.')
            await bot.post_message('mcv_rss', '启动器已更新' + file['latest']['snapshot'] + '快照。')
            addversion = open(version_file, 'a', encoding='utf-8')
            addversion.write('\n' + snapshot)
            addversion.close()
    except Exception:
        traceback.print_exc()


@on_schedule('mcv_jira_rss', developers=['OasisAkari', 'Dianliang233'],
             recommend_modules=['mcv_rss', 'mcbv_jira_rss', 'mcdv_jira_rss'],
             trigger=IntervalTrigger(seconds=60),
             desc='开启后当Jira更新Java版时将会自动推送消息。', alias='mcvjirarss')
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
                addversion = open(version_file, 'a', encoding='utf-8')
                addversion.write('\n' + release)
                addversion.close()
    except Exception:
        traceback.print_exc()


@on_schedule('mcbv_jira_rss',
             developers=['OasisAkari', 'Dianliang233'],
             recommend_modules=['mcv_rss', 'mcv_jira_rss', 'mcdv_jira_rss'],
             trigger=IntervalTrigger(seconds=60),
             desc='开启后当Jira更新基岩版时将会自动推送消息。', alias='mcbvjirarss')
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
                addversion = open(version_file, 'a', encoding='utf-8')
                addversion.write('\n' + release)
                addversion.close()
    except Exception:
        traceback.print_exc()


@on_schedule('mcdv_jira_rss',
             developers=['OasisAkari', 'Dianliang233'],
             recommend_modules=['mcv_rss', 'mcbv_jira_rss', 'mcv_jira_rss'],
             trigger=IntervalTrigger(seconds=60),
             desc='开启后当Jira更新Dungeons版本时将会自动推送消息。', alias='mcdvjirarss')
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
                addversion = open(version_file, 'a', encoding='utf-8')
                addversion.write('\n' + release)
                addversion.close()
    except Exception:
        traceback.print_exc()
