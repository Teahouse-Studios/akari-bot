import asyncio
import os
import re
import traceback

import aiohttp
from graia.application import MessageChain
from graia.application.message.elements.internal import Plain

from core.loader import logger_info
from database import BotDB
from modules.mcv.mcv import get_data

check_enable_modules_all = BotDB.check_enable_modules_all


def getfileversions(path):
    if not os.path.exists(path):
        a = open(path, 'a')
        a.close()
    w = open(path, 'r+')
    s = w.read().split('\n')
    w.close()
    return s

async def mcv_rss(app):
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    logger_info('Subbot ver launched')
    while True:
        try:
            version_file = os.path.abspath('./assets/mcversion.txt')
            logger_info('Checking mcv...')
            verlist = getfileversions(version_file)
            file = await get_data(url, 'json')
            release = file['latest']['release']
            snapshot = file['latest']['snapshot']
            if release not in verlist:
                logger_info(f'huh, we find {release}.')
                for qqgroup in check_enable_modules_all('group_permission', 'mcv_rss'):
                    try:
                        await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                            [Plain('启动器已更新' + file['latest']['release'] + '正式版。')]))
                        await asyncio.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
                for qqfriend in check_enable_modules_all('friend_permission', 'mcv_rss_self'):
                    try:
                        await app.sendFriendMessage(int(qqfriend), MessageChain.create(
                            [Plain('启动器已更新' + file['latest']['release'] + '正式版。')]))
                        await asyncio.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
                addversion = open(version_file, 'a')
                addversion.write('\n' + release)
                addversion.close()
                verlist = getfileversions(version_file)
            if snapshot not in verlist:
                logger_info(f'huh, we find {snapshot}.')
                for qqgroup in check_enable_modules_all('group_permission', 'mcv_rss'):
                    try:
                        await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                            [Plain('启动器已更新' + file['latest']['snapshot'] + '快照。')]))
                        await asyncio.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
                for qqfriend in check_enable_modules_all('friend_permission', 'mcv_rss_self'):
                    try:
                        await app.sendFriendMessage(int(qqfriend), MessageChain.create(
                            [Plain('启动器已更新' + file['latest']['snapshot'] + '快照。')]))
                        await asyncio.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
                addversion = open('./assets/mcversion.txt', 'a')
                addversion.write('\n' + snapshot)
                addversion.close()
            logger_info('mcv checked.')
            await asyncio.sleep(40)
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(20)


async def mcv_jira_rss(app):
    url = 'https://bugs.mojang.com/rest/api/2/project/10400/versions'
    logger_info('Subbot jira launched')
    while True:
        try:
            version_file = os.path.abspath('./assets/mcversion_jira.txt')
            logger_info('Checking Jira mcv...')
            verlist = getfileversions(version_file)
            file = await get_data(url, 'json')
            release = []
            for v in file:
                if not v['archived']:
                    release.append(v['name'])
            for x in release:
                if x not in verlist:
                    logger_info(f'huh, we find {x}.')
                    for qqgroup in check_enable_modules_all('group_permission', 'mcv_jira_rss'):
                        try:
                            await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                                [Plain(f'Jira已更新Java版{x}。\n（Jira上的信息仅作版本号预览用，不代表启动器已更新此版本）')]))
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                    for qqfriend in check_enable_modules_all('friend_permission', 'mcv_jira_rss_self'):
                        try:
                            await app.sendFriendMessage(int(qqfriend), MessageChain.create(
                                [Plain(f'Jira已更新Java版{x}。\n（Jira上的信息仅作版本号预览用，不代表启动器已更新此版本）')]))
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                    addversion = open(version_file, 'a')
                    addversion.write('\n' + x)
                    addversion.close()
            logger_info('jira mcv checked.')
            await asyncio.sleep(40)
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(20)


async def mcv_jira_rss_bedrock(app):
    url = 'https://bugs.mojang.com/rest/api/2/project/10200/versions'
    logger_info('Subbot jira-bedrock launched')
    while True:
        try:
            version_file = os.path.abspath('./assets/mcversion_jira-bedrock.txt')
            logger_info('Checking Jira mcv-bedrock...')
            verlist = getfileversions(version_file)
            file = await get_data(url, 'json')
            release = []
            for v in file:
                if not v['archived']:
                    release.append(v['name'])
            for x in release:
                if x not in verlist:
                    logger_info(f'huh, we find {x}.')
                    for qqgroup in check_enable_modules_all('group_permission', 'mcv_jira_rss'):
                        try:
                            await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                                [Plain(f'Jira已更新基岩版{x}。\n（Jira上的信息仅作版本号预览用，不代表商店已更新此版本）')]))
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                    for qqfriend in check_enable_modules_all('friend_permission', 'mcv_jira_rss_self'):
                        try:
                            await app.sendFriendMessage(int(qqfriend), MessageChain.create(
                                [Plain(f'Jira已更新基岩版{x}。\n（Jira上的信息仅作版本号预览用，不代表商店已更新此版本）')]))
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                    addversion = open(version_file, 'a')
                    addversion.write('\n' + x)
                    addversion.close()
            logger_info('jira mcv-bedrock checked.')
            await asyncio.sleep(90)
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(20)


async def mcv_jira_rss_dungeons(app):
    url = 'https://bugs.mojang.com/rest/api/2/project/11901/versions'
    logger_info('Subbot jira-dungeons launched')
    while True:
        try:
            version_file = os.path.abspath('./assets/mcversion_jira-dungeons.txt')
            logger_info('Checking Jira mcv-bedrock...')
            verlist = getfileversions(version_file)
            file = await get_data(url, 'json')
            release = []
            for v in file:
                if not v['archived']:
                    release.append(v['name'])
            for x in release:
                if x not in verlist:
                    logger_info(f'huh, we find {x}.')
                    for qqgroup in check_enable_modules_all('group_permission', 'mcv_jira_rss'):
                        try:
                            await app.sendGroupMessage(int(qqgroup), MessageChain.create(
                                [Plain(f'Jira已更新Dungeons {x}。\n（Jira上的信息仅作版本号预览用，不代表商店已更新此版本）')]))
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                    for qqfriend in check_enable_modules_all('friend_permission', 'mcv_jira_rss_self'):
                        try:
                            await app.sendFriendMessage(int(qqfriend), MessageChain.create(
                                [Plain(f'Jira已更新Dungeons {x}。\n（Jira上的信息仅作版本号预览用，不代表启动器已更新此版本）')]))
                            await asyncio.sleep(0.5)
                        except Exception:
                            traceback.print_exc()
                    addversion = open(version_file, 'a')
                    addversion.write('\n' + x)
                    addversion.close()
            logger_info('jira mcv-dungeons checked.')
            await asyncio.sleep(90)
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(20)

rss = {'mcv_rss': mcv_rss, 'mcv_jira_rss': mcv_jira_rss, 'mcv_bedrock_jira_rss': mcv_jira_rss_bedrock, 'mcv_dungeons_jira_rss': mcv_jira_rss_dungeons}
options = ['mcv_rss', 'mcv_jira_rss']
friend_options = ['mcv_rss_self', 'mcv_jira_rss_self']
alias = {'mcv_rss_self': 'mcv_rss', 'mcv_jira_rss_self': 'mcv_jira_rss'}
help = {'mcv_rss': {'help': '订阅Minecraft Java版游戏版本检测。'},
        'mcv_jira_rss': {'help': '订阅Minecraft Java版游戏版本检测（Jira记录，仅作预览用）。'}}
