import os
import re
import traceback
from urllib.parse import quote

import ujson as json
from bs4 import BeautifulSoup

from config import Config
from core.component import on_schedule
from core.elements import FetchTarget, IntervalTrigger, PrivateAssets
from core.logger import Logger
from core.utils import get_url

from google_play_scraper import app as google_play_scraper


def getfileversions(path):
    if not os.path.exists(path):
        a = open(path, 'a', encoding='utf-8')
        a.close()
    w = open(path, 'r+', encoding='utf-8')
    s = w.read().split('\n')
    w.close()
    return s


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
        link = f'https://www.minecraft.net/en-us/article/minecraft-' + re.sub("\.", "-", match_prerelease.group(1)) \
               + f'-pre-release-{match_prerelease.group(2)}'
    match_release_candidate = re.match(r'(.*?)-rc(.*[0-9])', version)
    if match_release_candidate:
        link = f'https://www.minecraft.net/en-us/article/minecraft-' + re.sub("\.", "-", match_release_candidate.group(1))\
               + f'-release-candidate-{match_release_candidate.group(2)}'
    if not link:
        link = 'https://www.minecraft.net/en-us/article/minecraft-java-edition-' + re.sub("\.", "-", version)
    webrender = Config('web_render')
    get = webrender + 'source?url=' + quote(link)

    try:
        html = await get_url(get)

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


@on_schedule('mcv_rss',
             developers=['OasisAkari', 'Dianliang233'],
             recommend_modules=['mcv_jira_rss', 'mcbv_jira_rss', 'mcdv_jira_rss'],
             trigger=IntervalTrigger(seconds=trigger_times),
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
            article = await get_article(release)
            if article[0] != '':
                await bot.post_message('minecraft_news', f'Minecraft官网发布了{release}的更新日志：\n' + article[0])
                newsfile = os.path.abspath(f'{PrivateAssets.path}/mcnews.txt')
                addnews = open(newsfile, 'a', encoding='utf-8')
                addnews.write('\n' + article[1])
                addnews.close()
        if snapshot not in verlist:
            Logger.info(f'huh, we find {snapshot}.')
            await bot.post_message('mcv_rss', '启动器已更新' + file['latest']['snapshot'] + '快照。')
            addversion = open(version_file, 'a', encoding='utf-8')
            addversion.write('\n' + snapshot)
            addversion.close()
            article = await get_article(snapshot)
            if article[0] != '':
                await bot.post_message('minecraft_news', f'Minecraft官网发布了{snapshot}的更新日志：\n' + article[0])
                newsfile = os.path.abspath(f'{PrivateAssets.path}/mcnews.txt')
                addnews = open(newsfile, 'a', encoding='utf-8')
                addnews.write('\n' + article[1])
                addnews.close()
    except Exception:
        traceback.print_exc()


@on_schedule('mcbv_rss', developers=['OasisAkari'],
             recommend_modules=['mcbv_jira_rss'],
             trigger=IntervalTrigger(seconds=trigger_times),
             desc='开启后当Minecraft基岩版商店更新时将会自动推送消息。', alias='mcbvrss')
async def mcbv_rss(bot: FetchTarget):
    try:
        version_file = os.path.abspath(f'{PrivateAssets.path}/mcbeversion.txt')
        verlist = getfileversions(version_file)
        version = (google_play_scraper('com.mojang.minecraftpe'))['version']
        if version not in verlist:
            Logger.info(f'huh, we find bedrock {version}.')
            await bot.post_message('mcbv_rss', '基岩版商店已更新' + version + '正式版。')
            addversion = open(version_file, 'a', encoding='utf-8')
            addversion.write('\n' + version)
            addversion.close()
    except Exception:
        traceback.print_exc()


@on_schedule('mcv_jira_rss', developers=['OasisAkari', 'Dianliang233'],
             recommend_modules=['mcv_rss', 'mcbv_jira_rss', 'mcdv_jira_rss'],
             trigger=IntervalTrigger(seconds=trigger_times),
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
             trigger=IntervalTrigger(seconds=trigger_times),
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
             trigger=IntervalTrigger(seconds=trigger_times),
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
