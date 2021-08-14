import asyncio
import json
import os
import traceback

from core.elements import FetchTarget
from core.loader.decorator import command
from core.logger import Logger
from core.scheduler import Scheduler
from core.utils import get_url
from database import BotDBUtil


def getfileversions(path):
    if not os.path.exists(path):
        a = open(path, 'a')
        a.close()
    w = open(path, 'r+')
    s = w.read().split('\n')
    w.close()
    return s


@command('mcv_rss', autorun=True)
async def mcv_rss(bot: FetchTarget):
    @Scheduler.scheduled_job('interval', seconds=30)
    async def java_main():
        url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
        try:
            version_file = os.path.abspath('./assets/mcversion.txt')
            Logger.info('Checking mcv...')
            verlist = getfileversions(version_file)
            file = json.loads(await get_url(url))
            release = file['latest']['release']
            snapshot = file['latest']['snapshot']
            if release not in verlist:
                Logger.info(f'huh, we find {release}.')
                get_target_id = BotDBUtil.Module.get_enabled_this('mcv_rss')
                for x in get_target_id:
                    fetch = bot.fetch_target(x)
                    if fetch:
                        try:
                            await fetch.sendMessage('启动器已更新' + file['latest']['release'] + '正式版。')
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                addversion = open(version_file, 'a')
                addversion.write('\n' + release)
                addversion.close()
                verlist = getfileversions(version_file)
            if snapshot not in verlist:
                Logger.info(f'huh, we find {snapshot}.')
                get_target_id = BotDBUtil.Module.get_enabled_this('mcv_rss')
                for x in get_target_id:
                    fetch = bot.fetch_target(x)
                    if fetch:
                        try:
                            await fetch.sendMessage('启动器已更新' + file['latest']['snapshot'] + '快照。')
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                addversion = open('./assets/mcversion.txt', 'a')
                addversion.write('\n' + snapshot)
                addversion.close()
            Logger.info('mcv checked.')
        except Exception:
            traceback.print_exc()


@command('mcv_jira_rss', autorun=True)
async def mcv_jira_rss(bot: FetchTarget):
    @Scheduler.scheduled_job('interval', seconds=30)
    async def java_jira():
        urls = {'Java版': 'https://bugs.mojang.com/rest/api/2/project/10400/versions',
                '基岩版': 'https://bugs.mojang.com/rest/api/2/project/10200/versions',
                'Minecraft Dungeons': 'https://bugs.mojang.com/rest/api/2/project/11901/versions'}
        for name in urls:
            try:
                version_file = os.path.abspath(f'./assets/mcjira_{name}.txt')
                Logger.info(f'Checking Jira mcv {name}...')
                verlist = getfileversions(version_file)
                file = json.loads(await get_url(urls[name]))
                releases = []
                for v in file:
                    if not v['archived']:
                        releases.append(v['name'])
                for release in releases:
                    if release not in verlist:
                        Logger.info(f'huh, we find {release}.')
                        verlist.append(release)
                        get_target_id = BotDBUtil.Module.get_enabled_this('mcv_jira_rss')
                        for id_ in get_target_id:
                            fetch = bot.fetch_target(id_)
                            if fetch:
                                send = await fetch.sendMessage(
                                    f'Jira已更新{name} {release}。\n（Jira上的信息仅作版本号预览用，不代表启动器已更新此版本）')
                        addversion = open(version_file, 'a')
                        addversion.write('\n' + release)
                        addversion.close()
                Logger.info('jira mcv checked.')
            except Exception:
                traceback.print_exc()
