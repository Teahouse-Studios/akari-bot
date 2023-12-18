import datetime
import re
import traceback
from urllib.parse import quote

import ujson as json
from bs4 import BeautifulSoup
from google_play_scraper import app as google_play_scraper

from config import CFG, Config
from core.builtins import I18NContext, FormattedTime
from core.logger import Logger
from core.queue import JobQueue
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.http import get_url
from core.utils.ip import IP
from core.utils.storedata import get_stored_list, update_stored_list

web_render = CFG.get_url('web_render')
web_render_local = CFG.get_url('web_render_local')


async def get_article(version, use_local=True):
    match_snapshot = re.match(r'.*?w.*', version)
    link = False
    if match_snapshot:
        link = 'https://www.minecraft.net/en-us/article/minecraft-snapshot-' + version
    match_prerelease1 = re.match(r'(.*?)-pre(.*[0-9])', version)
    match_prerelease2 = re.match(r'(.*?) Pre-Release (.*[0-9])', version)
    if match_prerelease1:
        match_prerelease = match_prerelease1
    elif match_prerelease2:
        match_prerelease = match_prerelease2
    else:
        match_prerelease = False
    if match_prerelease:
        link = f'https://www.minecraft.net/en-us/article/minecraft-' + re.sub("\\.", "-", match_prerelease.group(1)) \
               + f'-pre-release-{match_prerelease.group(2)}'
    match_release_candidate = re.match(r'(.*?)-rc(.*[0-9])', version)
    if match_release_candidate:
        link = f'https://www.minecraft.net/en-us/article/minecraft-' + re.sub("\\.", "-",
                                                                              match_release_candidate.group(1)) \
               + f'-release-candidate-{match_release_candidate.group(2)}'
    if not link:
        link = 'https://www.minecraft.net/en-us/article/minecraft-java-edition-' + re.sub("\\.", "-", version)
    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
            return '', ''
        use_local = False
    get = (web_render_local if use_local else web_render) + 'source?url=' + quote(link)

    try:
        html = await get_url(get, attempt=1)

        soup = BeautifulSoup(html, 'html.parser')

        title = soup.find('h1')
        if title.text == 'WE’RE SSSSSSSORRY':
            return '', ''
        else:
            return link, title.text
    except Exception:
        traceback.print_exc()
        return '', ''


trigger_times = 60 if not Config('slower_schedule') else 180


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcv_rss():
    url = 'https://piston-meta.mojang.com/mc/game/version_manifest.json'
    try:
        verlist = get_stored_list('scheduler', 'mcv_rss')
        file = json.loads(await get_url(url, attempt=1))
        release = file['latest']['release']
        snapshot = file['latest']['snapshot']
        time_release = 0
        time_snapshot = 0
        for v in file['versions']:
            if v['id'] == release:
                time_release = datetime.datetime.fromisoformat(v['releaseTime']).timestamp()
            if v['id'] == snapshot:
                time_snapshot = datetime.datetime.fromisoformat(v['releaseTime']).timestamp()

        if release not in verlist:
            Logger.info(f'huh, we find {release}.')

            await JobQueue.trigger_hook_all('mcv_rss',
                                            message=[I18NContext('mcv_rss.message.mcv_rss.release',
                                                                 version=release).to_dict(),
                                                     FormattedTime(time_release).to_dict()
                                                     ])
            verlist.append(release)
            update_stored_list('scheduler', 'mcv_rss', verlist)
            article = await get_article(release)
            if article[0] != '':
                get_stored_news_title = get_stored_list('scheduler', 'mcnews')
                if article[1] not in get_stored_news_title:
                    await JobQueue.trigger_hook_all('minecraft_news',
                                                    message=[I18NContext('minecraft_news.message.update_log',
                                                                         version=release,
                                                                         article=article[0]).to_dict()])
                    get_stored_news_title.append(article[1])
                    update_stored_list('scheduler', 'mcnews', get_stored_news_title)
        if snapshot not in verlist:
            Logger.info(f'huh, we find {snapshot}.')
            await JobQueue.trigger_hook_all('mcv_rss', message=[I18NContext('mcv_rss.message.mcv_rss.snapshot',
                                                                            version=file['latest'][
                                                                                'snapshot']).to_dict(),
                                                                FormattedTime(time_snapshot).to_dict()])
            verlist.append(snapshot)
            update_stored_list('scheduler', 'mcv_rss', verlist)
            article = await get_article(snapshot)
            if article[0] != '':
                get_stored_news_title = get_stored_list('scheduler', 'mcnews')
                if article[1] not in get_stored_news_title:
                    await JobQueue.trigger_hook_all('minecraft_news',
                                                    message=[I18NContext('minecraft_news.message.update_log',
                                                                         version=snapshot,
                                                                         article=article[0]).to_dict()])
                    get_stored_news_title.append(article[1])
                    update_stored_list('scheduler', 'mcnews', get_stored_news_title)
    except Exception:
        traceback.print_exc()


@Scheduler.scheduled_job(IntervalTrigger(seconds=180))
async def mcbv_rss():
    if IP.country == 'China' or IP.country is None:
        return  # 中国大陆无法访问Google Play商店
    try:
        verlist = get_stored_list('scheduler', 'mcbv_rss')
        version = google_play_scraper('com.mojang.minecraftpe')['version']
        if version not in verlist:
            Logger.info(f'huh, we find bedrock {version}.')
            await JobQueue.trigger_hook_all('mcbv_rss', message=[I18NContext('mcv_rss.message.mcbv_rss',
                                                                             version=version).to_dict()])
            verlist.append(version)
            update_stored_list('scheduler', 'mcbv_rss', verlist)
    except Exception:
        traceback.print_exc()


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcv_jira_rss():
    try:
        verlist = get_stored_list('scheduler', 'mcv_jira_rss')
        file = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/10400/versions', 200, attempt=1))
        releases = []
        for v in file:
            if not v['archived']:
                releases.append(v['name'])
            else:
                if v['name'] not in verlist:
                    verlist.append(v['name'])
        for release in releases:
            if release not in verlist:
                Logger.info(f'huh, we find {release}.')
                if release.lower().find('future version') != -1:
                    await JobQueue.trigger_hook_all('mcv_jira_rss',
                                                    message=[I18NContext('mcv_rss.message.mcv_jira_rss.future',
                                                                         version=release).to_dict()])
                else:
                    await JobQueue.trigger_hook_all('mcv_jira_rss', message=[I18NContext('mcv_rss.message.mcv_jira_rss',
                                                                                         version=release).to_dict()])
                verlist.append(release)
                update_stored_list('scheduler', 'mcv_jira_rss', verlist)

    except Exception:
        traceback.print_exc()


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcbv_jira_rss():
    try:
        verlist = get_stored_list('scheduler', 'mcbv_jira_rss')
        file = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/10200/versions', 200, attempt=1))
        releases = []
        for v in file:
            if not v['archived']:
                releases.append(v['name'])
            else:
                if v['name'] not in verlist:
                    verlist.append(v['name'])
        for release in releases:
            if release not in verlist:
                Logger.info(f'huh, we find {release}.')

                await JobQueue.trigger_hook_all('mcbv_jira_rss', message=[I18NContext('mcv_rss.message.mcbv_jira_rss',
                                                                                      version=release).to_dict()])
                verlist.append(release)
                update_stored_list('scheduler', 'mcbv_jira_rss', verlist)
    except Exception:
        traceback.print_exc()


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mcdv_jira_rss():
    try:
        verlist = get_stored_list('scheduler', 'mcdv_jira_rss')
        file = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/11901/versions', 200, attempt=1))
        releases = []
        for v in file:
            if not v['archived']:
                releases.append(v['name'])
            else:
                if v['name'] not in verlist:
                    verlist.append(v['name'])
        for release in releases:
            if release not in verlist:
                Logger.info(f'huh, we find {release}.')

                await JobQueue.trigger_hook_all('mcdv_jira_rss', message=[I18NContext('mcv_rss.message.mcdv_jira_rss',
                                                                                      version=release).to_dict()])
                verlist.append(release)
                update_stored_list('scheduler', 'mcdv_jira_rss', verlist)
    except Exception:
        traceback.print_exc()


@Scheduler.scheduled_job(IntervalTrigger(seconds=trigger_times))
async def mclgv_jira_rss():
    try:
        verlist = get_stored_list('scheduler', 'mclgv_jira_rss')
        file = json.loads(await get_url('https://bugs.mojang.com/rest/api/2/project/12200/versions', 200, attempt=1))
        releases = []
        for v in file:
            if not v['archived']:
                releases.append(v['name'])
            else:
                if v['name'] not in verlist:
                    verlist.append(v['name'])
        for release in releases:
            if release not in verlist:
                Logger.info(f'huh, we find {release}.')

                await JobQueue.trigger_hook_all('mclgv_jira_rss', message=[I18NContext('mcv_rss.message.mclgv_jira_rss',
                                                                                       version=release).to_dict()])
                verlist.append(release)
                update_stored_list('scheduler', 'mclgv_jira_rss', verlist)
    except Exception:
        traceback.print_exc()
