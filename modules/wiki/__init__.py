import asyncio
import re
import traceback
import urllib.parse
from typing import Union

import filetype
import ujson as json

from core.builtins.message import MessageSession
from core.component import on_command, on_regex
from core.dirty_check import check
from core.elements import Plain, Image, Voice, Url, confirm_command
from core.exceptions import AbuseWarning
from core.logger import Logger
from core.utils import download_to_cache
from core.utils.image_table import image_table_render, ImageTable
from .dbutils import WikiTargetInfo, Audit
from .getinfobox import get_pic
from .utils.ab import ab
from .utils.ab_qq import ab_qq
from .utils.newbie import newbie
from .utils.rc import rc
from .utils.rc_qq import rc_qq
from .wikilib import WikiLib, WhatAreUDoingError, PageInfo, InvalidWikiError, QueryInfo

wiki = on_command('wiki',
                  alias={'wiki_start_site': 'wiki set',
                         'interwiki': 'wiki iw'},
                  recommend_modules='wiki_inline',
                  developers=['OasisAkari'])


@wiki.handle('<PageName> [-l <lang>] {查询一个Wiki页面，若查询“随机页面”则随机一个页面。}',
             options_desc={'-l': '查找本页面的对应语言版本，若无结果则返回当前语言。'})
async def _(msg: MessageSession):
    get_lang: dict = msg.parsed_msg.get('-l', False)
    if get_lang:
        lang = get_lang['<lang>']
    else:
        lang = None
    await query_pages(msg, msg.parsed_msg['<PageName>'], lang=lang)


@wiki.handle('-p <PageID> [-i <CustomIW>]  {根据页面ID查询一个Wiki页面。}')
async def _(msg: MessageSession):
    if msg.parsed_msg.get('-i', False):
        iw: str = msg.parsed_msg['-i'].get('<CustomIW>', '')
    else:
        iw = ''
    page_id: str = msg.parsed_msg['<PageID>']
    if not page_id.isdigit():
        await msg.finish('错误：页面ID必须是数字。')
    Logger.debug(msg.parsed_msg)
    await query_pages(msg, pageid=page_id, iw=iw)


@wiki.handle('search <PageName> {搜索一个Wiki页面。}')
async def _(msg: MessageSession):
    await search_pages(msg, msg.parsed_msg['<PageName>'])


@wiki.handle('set <WikiUrl> {设置起始查询Wiki}', required_admin=True)
async def set_start_wiki(msg: MessageSession):
    target = WikiTargetInfo(msg)
    check = await WikiLib(msg.parsed_msg['<WikiUrl>'], headers=target.get_headers()).check_wiki_available()
    if check.available:
        if not check.value.in_blocklist or check.value.in_allowlist:
            result = WikiTargetInfo(msg).add_start_wiki(check.value.api)
            if result:
                await msg.finish(
                    f'成功添加起始Wiki：{check.value.name}' + ('\n' + check.message if check.message != '' else ''))
        else:
            await msg.finish(f'错误：{check.value.name}处于黑名单中。')
    else:
        result = '错误：无法添加此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@wiki.handle('iw (add|set) <Interwiki> <WikiUrl> {添加自定义Interwiki}', required_admin=True)
async def _(msg: MessageSession):
    iw = msg.parsed_msg['<Interwiki>']
    url = msg.parsed_msg['<WikiUrl>']
    target = WikiTargetInfo(msg)
    check = await WikiLib(url, headers=target.get_headers()).check_wiki_available()
    if check.available:
        if not check.value.in_blocklist or check.value.in_allowlist:
            result = target.config_interwikis(iw, check.value.api, let_it=True)
            if result:
                await msg.finish(f'成功：添加自定义Interwiki\n{iw} -> {check.value.name}')
        else:
            await msg.finish(f'错误：{check.value.name}处于黑名单中。')
    else:
        result = '错误：无法添加此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@wiki.handle('iw (del|delete|remove|rm) <Interwiki> {删除自定义Interwiki}', required_admin=True)
async def _(msg: MessageSession):
    iw = msg.parsed_msg['<Interwiki>']
    target = WikiTargetInfo(msg)
    result = target.config_interwikis(iw, let_it=False)
    if result:
        await msg.finish(f'成功：删除自定义Interwiki“{msg.parsed_msg["<Interwiki>"]}”')


@wiki.handle(['iw list {展示当前设置的Interwiki}', 'iw show {iw list的别名}',
              'iw (list|show) legacy {展示当前设置的Interwiki（旧版）}'])
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    start_wiki = target.get_start_wiki()
    base_interwiki_link = None
    if start_wiki is not None:
        base_interwiki_link = await WikiLib(start_wiki, target.get_headers()).parse_page_info('Special:Interwiki')
        if base_interwiki_link.status:
            base_interwiki_link = base_interwiki_link.link
    base_interwiki_link_msg = f'\n此处展示的是为机器人设定的自定义Interwiki，如需查看起始wiki的Interwiki，请见：{str(Url(base_interwiki_link))}'
    if query != {}:
        if 'legacy' not in msg.parsed_msg and msg.Feature.image:
            columns = [[x, query[x]] for x in query]
            img = await image_table_render(ImageTable(columns, ['Interwiki', 'Url']))
        else:
            img = False
        if img:
            mt = f'使用{msg.prefixes[0]}wiki iw get <Interwiki> 可以获取interwiki对应的链接。'
            if base_interwiki_link is not None:
                mt += base_interwiki_link_msg
            await msg.finish([Image(img), Plain(mt)])
        else:
            result = '当前设置了以下Interwiki：\n' + \
                     '\n'.join([f'{x}: {query[x]}' for x in query])
            if base_interwiki_link is not None:
                result += base_interwiki_link_msg
            await msg.finish(result)
    else:
        await msg.finish('当前没有设置任何Interwiki，使用~wiki iw add <interwiki> <api_endpoint_link>添加一个。')


@wiki.handle('iw get <Interwiki> {获取设置的Interwiki对应的api地址}')
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    if query != {}:
        if msg.parsed_msg['<Interwiki>'] in query:
            await msg.finish(Url(query[msg.parsed_msg['<Interwiki>']]))
        else:
            await msg.finish(f'未找到Interwiki：{msg.parsed_msg["<Interwiki>"]}')
    else:
        await msg.finish('当前没有设置任何Interwiki，使用~wiki iw add <interwiki> <api_endpoint_link>添加一个。')


@wiki.handle(['headers show {展示当前设置的headers}', 'headers list {headers show 的别名}'])
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    headers = target.get_headers()
    prompt = f'当前设置了以下标头：\n{json.dumps(headers)}\n如需自定义，请使用~wiki headers set <headers>。\n' \
             f'格式：\n' \
             f'~wiki headers set {{"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"}}'
    await msg.finish(prompt)


@wiki.handle('headers (add|set) <Headers> {添加自定义headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    add = target.config_headers(
        " ".join(msg.trigger_msg.split(" ")[3:]), let_it=True)
    if add:
        await msg.finish(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('headers (del|delete|remove|rm) <HeaderKey> {删除一个headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    delete = target.config_headers(
        [msg.parsed_msg['<HeaderHey>']], let_it=False)
    if delete:
        await msg.finish(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('headers reset {重置headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    reset = target.config_headers('{}', let_it=None)
    if reset:
        await msg.finish(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('prefix set <prefix> {设置查询自动添加前缀}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    prefix = msg.parsed_msg['<prefix>']
    set_prefix = target.set_prefix(prefix)
    if set_prefix:
        await msg.finish(f'成功更新请求时所使用的前缀：{prefix}')


@wiki.handle('prefix reset {重置查询自动添加的前缀}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    set_prefix = target.del_prefix()
    if set_prefix:
        await msg.finish(f'成功重置请求时所使用的前缀。')


@wiki.handle('fandom enable {禁用Fandom全局Interwiki查询}', 'fandom disable {禁用Fandom全局Interwiki查询}', required_admin=True)
async def _(msg: MessageSession):
    if msg.parsed_msg.get('enable', False):
        msg.data.edit_option('wiki_fandom_addon', True)
        await msg.finish('已启用Fandom全局Interwiki查询。')
    else:
        msg.data.edit_option('wiki_fandom_addon', False)
        await msg.finish('已禁用Fandom全局Interwiki查询。')


aud = on_command('wiki_audit', alias='wa',
                 developers=['Dianliang233', 'OasisAkari'], required_superuser=True)


@aud.handle(['trust <apiLink>', 'block <apiLink>'])
async def _(msg: MessageSession):
    req = msg.parsed_msg
    op = msg.session.sender
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check.available:
        api = check.value.api
        if req.get('trust', False):
            res = Audit(api).add_to_AllowList(op)
            list_name = '白'
        else:
            res = Audit(api).add_to_BlockList(op)
            list_name = '黑'
        if not res:
            await msg.finish(f'失败，此wiki已经存在于{list_name}名单中：' + api)
        else:
            await msg.finish(f'成功加入{list_name}名单：' + api)
    else:
        result = '错误：无法添加此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle(['distrust <apiLink>', 'unblock <apiLink>'])
async def _(msg: MessageSession):
    req = msg.parsed_msg
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check.available:
        api = check.value.api
        if req.get('distrust', False):
            res = Audit(api).remove_from_AllowList()
            list_name = '白'
        else:
            res = Audit(api).remove_from_BlockList()
            list_name = '黑'
        if not res:
            await msg.finish(f'失败，此wiki不存在于{list_name}名单中：' + api)
        else:
            await msg.finish(f'成功从{list_name}名单删除：' + api)
    else:
        result = '错误：无法查询此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle('query <apiLink>')
async def _(msg: MessageSession):
    req = msg.parsed_msg
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check.available:
        api = check.value.api
        audit = Audit(api)
        allow = audit.inAllowList
        block = audit.inBlockList
        msg_list = []
        if allow:
            msg_list.append(api + '已存在于白名单。')
        if block:
            msg_list.append(api + '已存在于黑名单。')
        if msg_list:
            msg_list.append('优先级：白名单 > 黑名单')
            await msg.finish('\n'.join(msg_list))
        else:
            await msg.finish(api + '不存在于任何名单。')
    else:
        result = '错误：无法查询此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle('list')
async def _(msg: MessageSession):
    allow_list = Audit.get_allow_list()
    block_list = Audit.get_block_list()
    legacy = True
    if msg.Feature.image:
        send_msgs = []
        allow_columns = [[x[0], x[1]] for x in allow_list]
        if allow_columns:
            allow_table = ImageTable(data=allow_columns, headers=[
                'APILink', 'Operator'])
            if allow_table:
                allow_image = await image_table_render(allow_table)
                if allow_image:
                    send_msgs.append(Plain('现有白名单：'))
                    send_msgs.append(Image(allow_image))
        block_columns = [[x[0], x[1]] for x in block_list]
        if block_columns:
            block_table = ImageTable(data=block_columns, headers=[
                'APILink', 'Operator'])
            if block_table:
                block_image = await image_table_render(block_table)
                if block_image:
                    send_msgs.append(Plain('现有黑名单：'))
                    send_msgs.append(Image(block_image))
        if send_msgs:
            await msg.finish(send_msgs)
            legacy = False
    if legacy:
        wikis = ['现有白名单：']
        for al in allow_list:
            wikis.append(f'{al[0]}（by {al[1]}）')
        wikis.append('现有黑名单：')
        for bl in block_list:
            wikis.append(f'{bl[0]}（by {bl[1]}）')
        await msg.finish('\n'.join(wikis))


wiki_inline = on_regex('wiki_inline',
                       desc='开启后将自动解析消息中带有的[[]]或{{}}字符串并自动查询Wiki，如[[海晶石]]',
                       alias='wiki_regex', developers=['OasisAkari'])


@wiki_inline.handle(re.compile(r'\[\[(.*?)]]', flags=re.I), mode='A')
async def _(msg: MessageSession):
    query_list = []
    for x in msg.matched_msg:
        if x != '' and x not in query_list and x[0] != '#':
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list, inline_mode=True)


@wiki_inline.handle(re.compile(r'\{\{(.*?)}}', flags=re.I), mode='A')
async def _(msg: MessageSession):
    query_list = []
    for x in msg.matched_msg:
        if x != '' and x not in query_list and x[0] != '#' and x.find("{") == -1:
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list, template=True, inline_mode=True)


@wiki_inline.handle(re.compile(r'≺(.*?)≻|⧼(.*?)⧽', flags=re.I), mode='A', show_typing=False)
async def _(msg: MessageSession):
    query_list = []
    for x in msg.matched_msg:
        for y in x:
            if y != '' and y not in query_list and y[0] != '#':
                query_list.append(y)
    if query_list:
        await query_pages(msg, query_list, mediawiki=True, inline_mode=True)


@wiki_inline.handle(re.compile(
    r'(https?://[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,4}\b[-a-zA-Z0-9@:%_+.~#?&/=]*)', flags=re.I),
    mode='A', show_typing=False)
async def _(msg: MessageSession):
    async def bgtask(msg: MessageSession):
        query_list = []
        target = WikiTargetInfo(msg)
        headers = target.get_headers()
        iws = target.get_interwikis()
        wikis = [target.get_start_wiki()] + [iws[w] for w in iws]
        Logger.debug(msg.matched_msg)
        for x in msg.matched_msg:
            if wiki_ := await WikiLib(x).check_wiki_available():
                if wiki_.available and wiki_.value.api in wikis:
                    query_list.append({x: wiki_.value})
        if query_list:
            for q in query_list:
                async def infobox():
                    if msg.Feature.image:
                        for qq in q:
                            get_infobox = await get_pic(q[qq].realurl, qq, headers, allow_special_page=q[qq].in_allowlist)
                            if get_infobox:
                                await msg.sendMessage(Image(get_infobox), quote=False)

                async def section():
                    if msg.Feature.image:
                        for qq in q:
                            section_ = []
                            quote_code = False
                            for qs in qq:
                                if qs == '#':
                                    quote_code = True
                                if qs == '?':
                                    quote_code = False
                                if quote_code:
                                    section_.append(qs)
                            if section_:
                                s = urllib.parse.unquote(''.join(section_)[1:])
                                if q[qq].realurl:
                                    get_section = await get_pic(q[qq].realurl, qq, headers, section=s)
                                    if get_section:
                                        await msg.sendMessage(Image(get_section))

                async def image_and_voice():
                    for qq in q:
                        articlepath = q[qq].articlepath.replace('$1', '(.*)')
                        get_title = re.sub(r'' + articlepath, '\\1', qq)
                        if get_title != '':
                            title = urllib.parse.unquote(get_title)
                            if not q[qq].in_allowlist:
                                for result in await check(title):
                                    if not result['status']:
                                        return

                            wiki_ = WikiLib(qq)
                            get_page = await wiki_.parse_page_info(title)
                            if get_page.status and get_page.file is not None:
                                dl = await download_to_cache(get_page.file)
                                guess_type = filetype.guess(dl)
                                if guess_type is not None:
                                    if guess_type.extension in ["png", "gif", "jpg", "jpeg", "webp", "bmp", "ico"]:
                                        if msg.Feature.image:
                                            await msg.sendMessage(Image(dl), quote=False)
                                    elif guess_type.extension in ["oga", "ogg", "flac", "mp3", "wav"]:
                                        if msg.Feature.voice:
                                            await msg.sendMessage(Voice(dl), quote=False)

                asyncio.create_task(infobox())
                asyncio.create_task(section())
                asyncio.create_task(image_and_voice())
    asyncio.create_task(bgtask(msg))


async def search_pages(session: MessageSession, title: Union[str, list, tuple], use_prefix=True):
    target = WikiTargetInfo(session)
    start_wiki = target.get_start_wiki()
    interwiki_list = target.get_interwikis()
    headers = target.get_headers()
    prefix = target.get_prefix()
    enabled_fandom_addon = session.options.get('wiki_fandom_addon')
    if start_wiki is None:
        await session.sendMessage(f'没有指定起始Wiki，已默认指定为中文Minecraft Wiki，发送{session.prefixes[0]}wiki set <域名>来设定自定义起始Wiki。'
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


async def query_pages(session: Union[MessageSession, QueryInfo], title: Union[str, list, tuple] = None,
                      pageid: str = None, iw: str = None, lang: str = None,
                      template=False, mediawiki=False, use_prefix=True, inline_mode=False, preset_message=None):
    if isinstance(session, MessageSession):
        target = WikiTargetInfo(session)
        start_wiki = target.get_start_wiki()
        interwiki_list = target.get_interwikis()
        headers = target.get_headers()
        prefix = target.get_prefix()
        enabled_fandom_addon = session.options.get('wiki_fandom_addon')
        if enabled_fandom_addon is None:
            enabled_fandom_addon = False
    elif isinstance(session, QueryInfo):
        start_wiki = session.api
        interwiki_list = []
        headers = session.headers
        prefix = session.prefix
        enabled_fandom_addon = False
    else:
        raise TypeError('session must be MessageSession or QueryInfo.')

    if start_wiki is None:
        if isinstance(session, MessageSession):
            await session.sendMessage(
                f'没有指定起始Wiki，已默认指定为中文Minecraft Wiki，发送{session.prefixes[0]}wiki set <域名>来设定自定义起始Wiki。'
                f'\n例子：{session.prefixes[0]}wiki set https://minecraft.fandom.com/zh/wiki/')
        start_wiki = 'https://minecraft.fandom.com/zh/api.php'
    if title is not None:
        if isinstance(title, str):
            title = [title]
        if len(title) > 15:
            raise AbuseWarning('一次性查询的页面超出15个。')
        query_task = {start_wiki: {'query': [], 'iw_prefix': ''}}
        for t in title:
            if prefix is not None and use_prefix:
                t = prefix + t
            if t[0] == ':':
                if len(t) > 1:
                    query_task[start_wiki]['query'].append(t[1:])
            else:
                match_interwiki = re.match(r'^(.*?):(.*)', t)
                matched = False
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
    elif pageid is not None:
        if iw == '':
            query_task = {start_wiki: {'queryid': [pageid], 'iw_prefix': ''}}
        else:
            query_task = {interwiki_list[iw]: {
                'queryid': [pageid], 'iw_prefix': iw}}
    else:
        raise ValueError('title or pageid must be specified.')
    Logger.debug(query_task)
    msg_list = []
    wait_msg_list = []
    wait_list = []
    wait_possible_list = []
    render_infobox_list = []
    render_section_list = []
    dl_list = []
    if preset_message is not None:
        msg_list.append(Plain(preset_message))
    for q in query_task:
        current_task = query_task[q]
        ready_for_query_pages = current_task['query'] if 'query' in current_task else []
        ready_for_query_ids = current_task['queryid'] if 'queryid' in current_task else []
        iw_prefix = (current_task['iw_prefix'] +
                     ':') if current_task['iw_prefix'] != '' else ''
        try:
            tasks = []
            for rd in ready_for_query_pages:
                if rd == '随机页面':
                    tasks.append(asyncio.create_task(
                        WikiLib(q, headers).random_page()))
                else:
                    if template:
                        rd = f'Template:{rd}'
                    if mediawiki:
                        rd = f'MediaWiki:{rd}'
                    tasks.append(asyncio.ensure_future(
                        WikiLib(q, headers).parse_page_info(title=rd, inline=inline_mode, lang=lang)))
            for rdp in ready_for_query_ids:
                tasks.append(asyncio.ensure_future(
                    WikiLib(q, headers).parse_page_info(pageid=rdp, inline=inline_mode, lang=lang)))
            query = await asyncio.gather(*tasks)
            for result in query:
                Logger.debug(result.__dict__)
                r: PageInfo = result
                display_title = None
                display_before_title = None
                if r.title is not None:
                    display_title = iw_prefix + r.title
                if r.before_title is not None:
                    display_before_title = iw_prefix + r.before_title
                new_possible_title_list = []
                if r.possible_research_title is not None:
                    for possible in r.possible_research_title:
                        new_possible_title_list.append(iw_prefix + possible)
                r.possible_research_title = new_possible_title_list
                if r.status:
                    plain_slice = []
                    if display_before_title is not None and display_before_title != display_title:
                        if r.before_page_property == 'template' and r.page_property == 'page':
                            plain_slice.append(
                                f'（[{display_before_title}]不存在，已自动重定向至[{display_title}]）')
                        else:
                            plain_slice.append(
                                f'（重定向[{display_before_title}] -> [{display_title}]）')
                    if r.desc is not None and r.desc != '':
                        plain_slice.append(r.desc)
                    if r.link is not None:
                        plain_slice.append(
                            str(Url(r.link, use_mm=not r.info.in_allowlist)))
                    if plain_slice:
                        msg_list.append(Plain('\n'.join(plain_slice)))
                    if r.file is not None:
                        dl_list.append(r.file)
                    else:
                        if r.link is not None and r.section is None:
                            render_infobox_list.append(
                                {r.link: {'url': r.info.realurl, 'in_allowlist': r.info.in_allowlist}})
                        elif r.link is not None and r.section is not None and r.info.in_allowlist:
                            render_section_list.append(
                                {r.link: {'url': r.info.realurl, 'section': r.section}})
                else:
                    plain_slice = []
                    wait_plain_slice = []
                    if display_title is not None and display_before_title is not None:
                        if isinstance(session, MessageSession) and session.Feature.wait:
                            if len(r.possible_research_title) > 1:
                                wait_plain_slice.append(
                                    f'提示：[{display_before_title}]不存在，您是否想要找的是：')
                                pi = 0
                                for p in r.possible_research_title:
                                    pi += 1
                                    wait_plain_slice.append(
                                        f'{pi}. {p}')
                                wait_plain_slice.append(f'请回复指定序号获取对应内容，若回复“是”，'
                                                        f'则默认选择{str(r.possible_research_title.index(display_title) + 1)}号内容。')
                                wait_possible_list.append({display_before_title: {display_title: r.possible_research_title}})
                            else:
                                wait_plain_slice.append(
                                    f'提示：[{display_before_title}]不存在，您是否想要找的是[{display_title}]？')
                        else:
                            wait_plain_slice.append(
                                f'提示：[{display_before_title}]不存在，您可能要找的是：[{display_title}]。')
                        if len(r.possible_research_title) == 1:
                            wait_list.append({display_title: display_before_title})
                    elif r.before_title is not None:
                        plain_slice.append(f'提示：找不到[{display_before_title}]。')
                    elif r.id != -1:
                        plain_slice.append(f'提示：找不到ID为{str(r.id)}的页面。')
                    if r.desc is not None and r.desc != '':
                        plain_slice.append(r.desc)
                    if r.invalid_namespace and r.before_title is not None:
                        plain_slice.append(
                            f'此Wiki上没有名为{r.invalid_namespace}的命名空间，请检查拼写后再试。')
                    if r.before_page_property == 'template':
                        if r.before_title.split(':')[1].isupper():
                            plain_slice.append(
                                f'提示：机器人暂不支持魔术字。')
                    if plain_slice:
                        msg_list.append(Plain('\n'.join(plain_slice)))
                    if wait_plain_slice:
                        wait_msg_list.append(
                            Plain('\n'.join(wait_plain_slice)))
        except WhatAreUDoingError:
            raise AbuseWarning('使机器人重定向页面的次数过多。')
        except InvalidWikiError as e:
            if isinstance(session, MessageSession):
                await session.sendMessage(f'发生错误：' + str(e))
            else:
                msg_list.append(Plain(f'发生错误：' + str(e)))
    if isinstance(session, MessageSession):
        if msg_list:
            if all([not render_infobox_list, not render_section_list, not dl_list, not wait_list, not wait_possible_list]):
                await session.finish(msg_list)
            else:
                await session.sendMessage(msg_list)

        async def infobox():
            if render_infobox_list and session.Feature.image:
                infobox_msg_list = []
                for i in render_infobox_list:
                    for ii in i:
                        get_infobox = await get_pic(i[ii]['url'], ii, headers, allow_special_page=i[ii]['in_allowlist'])
                        if get_infobox:
                            infobox_msg_list.append(Image(get_infobox))
                if infobox_msg_list:
                    await session.sendMessage(infobox_msg_list, quote=False)

        async def section():
            if render_section_list and session.Feature.image:
                section_msg_list = []
                for i in render_section_list:
                    for ii in i:
                        if i[ii]['in_allowlist']:
                            get_section = await get_pic(i[ii]['url'], ii, headers, section=i[ii]['section'])
                            if get_section:
                                section_msg_list.append(Image(get_section))
                if section_msg_list:
                    await session.sendMessage(section_msg_list, quote=False)

        async def image_and_voice():
            if dl_list:
                for f in dl_list:
                    dl = await download_to_cache(f)
                    guess_type = filetype.guess(dl)
                    if guess_type is not None:
                        if guess_type.extension in ["png", "gif", "jpg", "jpeg", "webp", "bmp", "ico"]:
                            if session.Feature.image:
                                await session.sendMessage(Image(dl), quote=False)
                        elif guess_type.extension in ["oga", "ogg", "flac", "mp3", "wav"]:
                            if session.Feature.voice:
                                await session.sendMessage(Voice(dl), quote=False)

        async def wait_confirm():
            if wait_msg_list and session.Feature.wait:
                confirm = await session.waitNextMessage(wait_msg_list, delete=True)
                auto_index = False
                index = 0
                if confirm.asDisplay() in confirm_command:
                    auto_index = True
                elif confirm.asDisplay().isdigit():
                    index = int(confirm.asDisplay()) - 1
                else:
                    return
                preset_message = []
                wait_list_ = []
                for w in wait_list:
                    for wd in w:
                        preset_message.append(f'（已指定[{w[wd]}]更正为[{wd}]。）')
                        wait_list_.append(wd)
                if auto_index:
                    for wp in wait_possible_list:
                        for wpk in wp:
                            keys = list(wp[wpk].keys())
                            preset_message.append(f'（已指定[{wpk}]更正为[{keys[0]}]。）')
                            wait_list_.append(keys[0])
                else:
                    for wp in wait_possible_list:
                        for wpk in wp:
                            keys = list(wp[wpk].keys())
                            if len(wp[wpk][keys[0]]) > index:
                                preset_message.append(f'（已指定[{wpk}]更正为[{wp[wpk][keys[0]][index]}]。）')
                                wait_list_.append(wp[wpk][keys[0]][index])

                if wait_list_:
                    await query_pages(session, wait_list_, use_prefix=False, preset_message='\n'.join(preset_message),
                                      lang=lang)
        asyncio.create_task(infobox())
        asyncio.create_task(section())
        asyncio.create_task(image_and_voice())
        asyncio.create_task(wait_confirm())
    else:
        return {'msg_list': msg_list, 'web_render_list': render_infobox_list, 'dl_list': dl_list,
                'wait_list': wait_list, 'wait_msg_list': wait_msg_list}


rc_ = on_command('rc', desc='获取默认wiki的最近更改', developers=['OasisAkari'])


@rc_.handle()
async def rc_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.finish('未设置起始wiki。')
    legacy = True
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        try:
            nodelist = await rc_qq(start_wiki)
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            traceback.print_exc()
            await msg.finish('无法发送转发消息，已自动回滚至传统样式。')
            legacy = True
    if legacy:
        res = await rc(start_wiki)
        await msg.finish(res)


a = on_command('ab', desc='获取默认wiki的最近滥用日志', developers=['OasisAkari'])


@a.handle()
async def ab_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.finish('未设置起始wiki。')
    legacy = True
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        try:
            nodelist = await ab_qq(start_wiki)
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            traceback.print_exc()
            await msg.finish('无法发送转发消息，已自动回滚至传统样式。')
            legacy = True
    if legacy:
        res = await ab(start_wiki)
        await msg.finish(res)


n = on_command('newbie', desc='获取默认wiki的新用户', developers=['OasisAkari'])


@n.handle()
async def newbie_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.finish('未设置起始wiki。')
    res = await newbie(start_wiki)
    await msg.finish(res)
