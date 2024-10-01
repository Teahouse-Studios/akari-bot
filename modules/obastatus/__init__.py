from core.builtins import Bot, Image, Plain
from core.component import module
from core.utils.http import get_url

import re
from config import Config
from datetime import datetime

API_URL = Config('apiurl', 'https://bd.bangbang93.com/openbmclapi')
NOTFOUND_IMG = Config('notfoundimg', 'https://http.cat/404.jpg')

obastatus = module(
    bind_prefix='obastatus',
    desc='{obastatus.help.desc}',
    alias='oba',
    developers=['WorldHim'],
    support_languages=['zh_cn'],
)

async def sizeConvert(value):
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    size = 1024.0
    for i in range(len(units)):
        if(value / size) < 1:
            return '%.2f%s' % (value, ' ' + units[i])
        value /= size

async def latestVersion():
    version = await get_url(f'{API_URL}/metric/version',
                            fmt='json')
    return f'''{version.get('version')}@{version.get('_resolved').split('#')[1][:7]}'''

async def searchCluster(clusterList: dict, key: str, value):
    result = []
    regex = re.compile(value, re.IGNORECASE)

    for (rank, cluster) in enumerate(clusterList, 1):
        if regex.search(cluster.get(key)):
            result.append((rank, cluster))

    return result

@obastatus.command('{{obastatus.help.status}}')
@obastatus.command('status {{obastatus.help.status}}')
async def status(msg: Bot.MessageSession):
    dashboard = await get_url(f'{API_URL}/metric/dashboard',
                              fmt='json')

    message = f'''{msg.locale.t('obastatus.message.status',
                                currentNodes = dashboard.get('currentNodes'),
                                load = round(dashboard.get('load') * 100, 2),
                                bandwidth = dashboard.get('bandwidth'),
                                currentBandwidth = round(dashboard.get('currentBandwidth'), 2),
                                hits = dashboard.get('hits'),
                                size = await sizeConvert(dashboard.get('bytes')))}
{msg.locale.t('obastatus.message.version', version = await latestVersion())}
{msg.locale.t('obastatus.message.queryTime', queryTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}'''

    await msg.finish(message)

@obastatus.command('rank [<rank>] {{obastatus.help.rank}}')
async def rank(msg: Bot.MessageSession, rank: int = 1):
    rankList = await get_url(f'{API_URL}/metric/rank',
                             fmt='json')
    cluster = rankList[rank - 1]

    message = f'''{'🟩' if cluster.get('isEnabled') else '🟥'}
{msg.locale.t('obastatus.message.cluster',
              name = cluster.get('name'),
              id = cluster.get('_id'),
              hits = cluster.get('metric').get('hits'),
              size = await sizeConvert(cluster.get('metric').get('bytes')))}
{msg.locale.t('obastatus.message.queryTime', queryTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}'''

    if 'sponsor' not in cluster:
        await msg.finish(message)
    else:
        await msg.send_message(message)
        sponsor = cluster.get('sponsor')

        message = msg.locale.t('obastatus.message.sponsor',
                               name = sponsor.get('name'),
                               url = sponsor.get('url'))

        try:
            await msg.finish([Plain(message), Image(str(sponsor.get('banner')))])
        except Exception:
            await msg.finish(message)

@obastatus.command('top [<rank>] {{obastatus.help.top}}')
async def top(msg: Bot.MessageSession, rank: int = 10):
    rankList = await get_url(f'{API_URL}/metric/rank',
                             fmt='json')

    message = ''

    for i in range(0, rank):
        cluster = rankList[i]

        sponsor = cluster.get('sponsor', '未知')
        
        try:
            sponsor_name = sponsor.get('name')
        except AttributeError:
            sponsor_name = '未知'

        try:
            message += '🟩 | ' if cluster.get('isEnabled') else '🟥 | '
            message += msg.locale.t('obastatus.message.top',
                                    rank = i + 1,
                                    name = cluster.get('name'),
                                    id = cluster.get('_id'),
                                    hits = cluster.get('metric').get('hits'),
                                    size = await sizeConvert(cluster.get('metric').get('bytes')),
                                    sponsor_name = sponsor_name)
        except KeyError:
            break

        message += '\n'

    message = message.rstrip()

    await msg.finish(message)

@obastatus.command('search <context> {{obastatus.help.search}}')
async def search(msg: Bot.MessageSession, context: str):
    rankList = await get_url(f'{API_URL}/metric/rank',
                                fmt='json')

    clusterList = await searchCluster(rankList, 'name', context)

    message = ''

    for rank, cluster in clusterList:
        sponsor = cluster.get('sponsor', '未知')
        
        try:
            sponsor_name = sponsor.get('name')
        except AttributeError:
            sponsor_name = '未知'

        try:
            message += '🟩 | ' if cluster.get('isEnabled') else '🟥 | '
            message += msg.locale.t('obastatus.message.top',
                                    rank = rank,
                                    name = cluster.get('name'),
                                    id = cluster.get('_id'),
                                    hits = cluster.get('metric').get('hits'),
                                    size = await sizeConvert(cluster.get('metric').get('bytes')),
                                    sponsor_name = sponsor_name)
        except KeyError:
            break

        message += '\n'

    message = message.rstrip()

    if message:
        await msg.finish(message)
    else:
        await msg.finish(Image(NOTFOUND_IMG))

@obastatus.command('sponsor {{obastatus.help.sponsor}}')
async def sponsor(msg: Bot.MessageSession):
    sponsor = await get_url(f'{API_URL}/sponsor',
                            fmt='json')
    cluster = await get_url(f'{API_URL}/sponsor/' + str(sponsor['_id']),
                            fmt='json')
    message = msg.locale.t('obastatus.message.sponsor',
                           name = cluster.get('name'),
                           url = cluster.get('url'))

    try:
        await msg.finish([Plain(message), Image(str(cluster.get('banner')))])
    except Exception:
        await msg.finish(message)