import asyncio
import re
from typing import Union

from core.builtins.message import MessageSession
from core.elements import Plain
from core.logger import Logger
from modules.wiki.utils.dbutils import WikiTargetInfo
from modules.wiki.utils.wikilib import WikiLib
from .wiki import wiki, query_pages


@wiki.handle('search <PageName> {搜索一个Wiki页面。}')
async def _(msg: MessageSession):
    await search_pages(msg, msg.parsed_msg['<PageName>'])


async def search_pages(session: MessageSession, title: Union[str, list, tuple], use_prefix=True):
    target = WikiTargetInfo(session)
    start_wiki = target.get_start_wiki()
    interwiki_list = target.get_interwikis()
    headers = target.get_headers()
    prefix = target.get_prefix()
    enabled_fandom_addon = session.options.get('wiki_fandom_addon')
    if start_wiki is None:
        await session.sendMessage(
            f'没有指定起始Wiki，已默认指定为中文Minecraft Wiki，发送{session.prefixes[0]}wiki set <域名>来设定自定义起始Wiki。'
            f'\n例子：{session.prefixes[0]}wiki set https://minecraft.fandom.com/zh/wiki/')
        start_wiki = 'https://minecraft.fandom.com/zh/api.php'
    if isinstance(title, str):
        title = [title]
    query_task = {start_wiki: {'query': [], 'iw_prefix': ''}}
    for t in title:
        if prefix is not None and use_prefix:
            t = prefix + t
        if t[0] == ':':
            if len(t) > 1:
                query_task[start_wiki]['query'].append(t[1:])
        else:
            matched = False
            match_interwiki = re.match(r'^(.*?):(.*)', t)
            if match_interwiki:
                g1 = match_interwiki.group(1)
                g2 = match_interwiki.group(2)
                if g1 in interwiki_list:
                    interwiki_url = interwiki_list[g1]
                    if interwiki_url not in query_task:
                        query_task[interwiki_url] = {
                            'query': [], 'iw_prefix': g1}
                    query_task[interwiki_url]['query'].append(g2)
                    matched = True
                elif g1 == 'w' and enabled_fandom_addon:
                    if match_interwiki := re.match(r'(.*?):(.*)', match_interwiki.group(2)):
                        if match_interwiki.group(1) == 'c':
                            if match_interwiki := re.match(r'(.*?):(.*)', match_interwiki.group(2)):
                                interwiki_split = match_interwiki.group(
                                    1).split('.')
                                if len(interwiki_split) == 2:
                                    get_link = f'https://{interwiki_split[1]}.fandom.com/api.php'
                                    find = interwiki_split[0] + \
                                           ':' + match_interwiki.group(2)
                                    iw = 'w:c:' + interwiki_split[0]
                                else:
                                    get_link = f'https://{match_interwiki.group(1)}.fandom.com/api.php'
                                    find = match_interwiki.group(2)
                                    iw = 'w:c:' + match_interwiki.group(1)
                                if get_link not in query_task:
                                    query_task[get_link] = {
                                        'query': [], 'iw_prefix': iw}
                                query_task[get_link]['query'].append(find)
                                matched = True
            if not matched:
                query_task[start_wiki]['query'].append(t)
    Logger.debug(query_task)
    msg_list = []
    wait_msg_list = []
    for q in query_task:
        current_task = query_task[q]
        ready_for_query_pages = current_task['query'] if 'query' in current_task else []
        iw_prefix = (current_task['iw_prefix'] +
                     ':') if current_task['iw_prefix'] != '' else ''
        tasks = []
        for rd in ready_for_query_pages:
            tasks.append(asyncio.ensure_future(
                WikiLib(q, headers).search_page(rd)))
        query = await asyncio.gather(*tasks)
        for result in query:
            for r in result:
                wait_msg_list.append(iw_prefix + r)
    if len(wait_msg_list) != 0:
        msg_list.append('查询到以下结果：')
        i = 0
        for w in wait_msg_list:
            i += 1
            w = f'{i}. {w}'
            msg_list.append(w)
        msg_list.append('回复编号以查询对应的页面。')
    reply = await session.waitReply(Plain('\n'.join(msg_list)))
    if reply.asDisplay().isdigit():
        reply_number = int(reply.asDisplay()) - 1
        await query_pages(reply, wait_msg_list[reply_number])
