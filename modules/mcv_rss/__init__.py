import re
import traceback
from urllib.parse import quote

import ujson as json
from bs4 import BeautifulSoup
from google_play_scraper import app as google_play_scraper

from config import Config
from core.builtins import Bot
from core.component import module
from core.logger import Logger
from core.scheduler import IntervalTrigger
from core.utils.http import get_url
from core.utils.ip import IP
from core.utils.storedata import get_stored_list, update_stored_list


async def get_article(version):
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
    webrender = Config('web_render')
    if not webrender:
        return
    get = webrender + '/source?url=' + quote(link)

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


bot = Bot.FetchTarget

trigger_times = 60 if not Config('slower_schedule') else 180

mcv_rss = module('mcv_rss',
                 developers=['OasisAkari', 'Dianliang233'],
                 recommend_modules=['mcv_jira_rss', 'mcbv_jira_rss', 'mcdv_jira_rss'],
                 desc='{mcv_rss.help.mcv_rss.desc}', alias='mcvrss')


@mcv_rss.handle(IntervalTrigger(seconds=trigger_times))
async def mcv_rss():
    url = 'https://piston-meta.mojang.com/mc/game/version_manifest.json'
    try:
        verlist = get_stored_list(bot, 'mcv_rss')
        file = json.loads(await get_url(url, attempt=1))
        release = file['latest']['release']
        snapshot = file['latest']['snapshot']
        if release not in verlist:
            Logger.info(f'huh, we find {release}.')
            await bot.post_message('mcv_rss', 'mcv_rss.message.mcv_rss.release', i18n=True, version=file['latest']['release'])
            verlist.append(release)
            update_stored_list(bot, 'mcv_rss', verlist)
            article = await get_article(release)
            if article[0] != '':
                get_stored_news_title = get_stored_list(bot, 'mcnews')
                if article[1] not in get_stored_news_title:
                    await bot.post_message('minecraft_news', 'minecraft_news.message.update_log', i18n=True, version=release, article=article[0])
                    get_stored_news_title.append(article[1])
                    update_stored_list(bot, 'mcnews', get_stored_news_title)
        if snapshot not in verlist:
            Logger.info(f'huh, we find {snapshot}.')
            await bot.post_message('mcv_rss', 'mcv_rss.message.mcv_rss.snapshot', i18n=True, version=file['latest']['snapshot'])
            verlist.append(snapshot)
            update_stored_list(bot, 'mcv_rss', verlist)
            article = await get_article(snapshot)
            if article[0] != '':
                get_stored_news_title = get_stored_list(bot, 'mcnews')
                if article[1] not in get_stored_news_title:
                    await bot.post_message('minecraft_news', 'minecraft_news.message.update_log', i18n=True, version=snapshot, article=article[0])
                    get_stored_news_title.append(article[1])
                    update_stored_list(bot, 'mcnews', get_stored_news_title)
    except Exception:
        traceback.print_exc()


mcbv_rss = module('mcbv_rss', developers=['OasisAkari'],
                  recommend_modules=['mcbv_jira_rss'],
                  desc='{mcv_rss.help.mcbv_rss.desc}', alias='mcbvrss')


@mcbv_rss.handle(IntervalTrigger(seconds=180))
async def mcbv_rss():
    if IP.country == 'China' or IP.country is None:
        return  # 中国大陆无法访问Google Play商店
    try:
        verlist = get_stored_list(bot, 'mcbv_rss')
        version = google_play_scraper('com.mojang.minecraftpe')['version']
        if version not in verlist:
            Logger.info(f'huh, we find bedrock {version}.')
            await bot.post_message('mcbv_rss', 'mcv_rss.message.mcbv_rss', i18n=True, version=version)
            verlist.append(version)
            update_stored_list(bot, 'mcbv_rss', verlist)
    except Exception:
        traceback.print_exc()


mcv_jira_rss = module('mcv_jira_rss', developers=['OasisAkari', 'Dianliang233'],
                      recommend_modules=['mcv_rss', 'mcbv_jira_rss', 'mcdv_jira_rss'],
                      desc='{mcv_rss.help.mcv_jira_rss.desc}', alias='mcvjirarss')


@mcv_jira_rss.handle(IntervalTrigger(seconds=trigger_times))
async def mcv_jira_rss():
    try:
        verlist = get_stored_list(bot, 'mcv_jira_rss')
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
                    await bot.post_message('mcv_jira_rss', 'mcv_rss.message.mcv_jira_rss.future', i18n=True, version=release)
                else:
                    await bot.post_message('mcv_jira_rss', 'mcv_rss.message.mcv_jira_rss', i18n=True, version=release)
                verlist.append(release)
                update_stored_list(bot, 'mcv_jira_rss', verlist)

    except Exception:
        traceback.print_exc()


mcbv_jira_rss = module('mcbv_jira_rss',
                       developers=['OasisAkari', 'Dianliang233'],
                       recommend_modules=['mcv_rss', 'mcv_jira_rss', 'mcdv_jira_rss'],
                       desc='{mcv_rss.help.mcbv_jira_rss.desc}', alias='mcbvjirarss')


@mcbv_jira_rss.handle(IntervalTrigger(seconds=trigger_times))
async def mcbv_jira_rss():
    try:
        verlist = get_stored_list(bot, 'mcbv_jira_rss')
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

                await bot.post_message('mcbv_jira_rss', 'mcv_rss.message.mcbv_jira_rss', i18n=True, version=release)
                verlist.append(release)
                update_stored_list(bot, 'mcbv_jira_rss', verlist)
    except Exception:
        traceback.print_exc()


mcdv_jira_rss = module('mcdv_jira_rss',
                       developers=['OasisAkari', 'Dianliang233'],
                       recommend_modules=['mcv_rss', 'mcbv_jira_rss', 'mcv_jira_rss'],
                       desc='{mcv_rss.help.mcdv_jira_rss.desc}', alias='mcdvjirarss')


@mcdv_jira_rss.handle(IntervalTrigger(seconds=trigger_times))
async def mcdv_jira_rss():
    try:
        verlist = get_stored_list(bot, 'mcdv_jira_rss')
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

                await bot.post_message('mcdv_jira_rss', 'mcv_rss.message.mcdv_jira_rss', i18n=True, version=release)
                verlist.append(release)
                update_stored_list(bot, 'mcdv_jira_rss', verlist)
    except Exception:
        traceback.print_exc()
