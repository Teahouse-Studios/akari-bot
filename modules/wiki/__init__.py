import asyncio
import re
import traceback
from typing import Union

import filetype
import ujson as json

from core.component import on_command, on_regex, on_option
from core.elements import MessageSession, Plain, Image, Voice
from core.exceptions import AbuseWarning
from core.utils import download_to_cache
from core.utils.image_table import image_table_render, ImageTable
from database import BotDBUtil
from .dbutils import WikiTargetInfo, Audit
from .getinfobox import get_infobox_pic
from .utils.ab import ab
from .utils.ab_qq import ab_qq
from .utils.newbie import newbie
from .utils.rc import rc
from .utils.rc_qq import rc_qq
from .wikilib_v2 import WikiLib, WhatAreUDoingError, PageInfo, InvalidWikiError

wiki = on_command('wiki',
                  alias={'wiki_start_site': 'wiki set', 'interwiki': 'wiki iw'},
                  recommend_modules='wiki_inline',
                  developers=['OasisAkari'])


@wiki.handle('<PageName> {搜索一个Wiki页面，若搜索“随机页面”则随机一个页面。}')
async def _(msg: MessageSession):
    await query_pages(msg, msg.parsed_msg['<PageName>'])


@wiki.handle('set <WikiUrl> {设置起始查询Wiki}', required_admin=True)
async def set_start_wiki(msg: MessageSession):
    target = WikiTargetInfo(msg)
    check = await WikiLib(msg.parsed_msg['<WikiUrl>'], headers=target.get_headers()).check_wiki_available()
    if check.available:
        if not check.value.in_blocklist or check.value.in_allowlist:
            result = WikiTargetInfo(msg).add_start_wiki(check.value.api)
            if result:
                await msg.sendMessage(
                    f'成功添加起始Wiki：{check.value.name}' + ('\n' + check.message if check.message != '' else ''))
        else:
            await msg.sendMessage(f'错误：{check.value.name}处于黑名单中。')
    else:
        result = '错误：无法添加此Wiki。' + ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.sendMessage(result)


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
                await msg.sendMessage(f'成功：添加自定义Interwiki\n{iw} -> {check.value.name}')
        else:
            await msg.sendMessage(f'错误：{check.value.name}处于黑名单中。')
    else:
        result = '错误：无法添加此Wiki。' + ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.sendMessage(result)


@wiki.handle('iw (del|delete|remove|rm) <Interwiki> {删除自定义Interwiki}', required_admin=True)
async def _(msg: MessageSession):
    iw = msg.parsed_msg['<Interwiki>']
    target = WikiTargetInfo(msg)
    result = target.config_interwikis(iw, let_it=False)
    if result:
        await msg.sendMessage(f'成功：删除自定义Interwiki“{msg.parsed_msg["<Interwiki>"]}”')


@wiki.handle(['iw list {展示当前设置的Interwiki}', 'iw show {iw list的别名}',
              'iw (list|show) legacy {展示当前设置的Interwiki（旧版）}'])
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    if query != {}:
        if not msg.parsed_msg['legacy'] and msg.Feature.image:
            columns = [[x, query[x]] for x in query]
            img = await image_table_render(ImageTable(columns, ['Interwiki', 'Url']))
        else:
            img = False
        if img:
            await msg.sendMessage([Image(img), Plain(f'使用~wiki iw get <Interwiki> 可以获取interwiki对应的链接。')])
        else:
            result = '当前设置了以下Interwiki：\n' + '\n'.join([f'{x}: {query[x]}' for x in query])
            await msg.sendMessage(result)
    else:
        await msg.sendMessage('当前没有设置任何Interwiki，使用~wiki iw add <interwiki> <api_endpoint_link>添加一个。')


@wiki.handle('iw get <Interwiki> {获取设置的Interwiki对应的api地址}')
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    if query != {}:
        if msg.parsed_msg['<Interwiki>'] in query:
            await msg.sendMessage(query[msg.parsed_msg['<Interwiki>']])
        else:
            await msg.sendMessage(f'未找到Interwiki：{msg.parsed_msg["<Interwiki>"]}')
    else:
        await msg.sendMessage('当前没有设置任何Interwiki，使用~wiki iw add <interwiki> <api_endpoint_link>添加一个。')


@wiki.handle(['headers show {展示当前设置的headers}', 'headers list {headers show 的别名}'])
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    headers = target.get_headers()
    prompt = f'当前设置了以下标头：\n{json.dumps(headers)}\n如需自定义，请使用~wiki headers set <headers>。\n' \
             f'格式：\n' \
             f'~wiki headers set {{"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"}}'
    await msg.sendMessage(prompt)


@wiki.handle('headers (add|set) <Headers> {添加自定义headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    add = target.config_headers(" ".join(msg.trigger_msg.split(" ")[3:]), let_it=True)
    if add:
        await msg.sendMessage(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('headers (del|delete|remove|rm) <HeaderKey> {删除一个headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    delete = target.config_headers([msg.parsed_msg['<HeaderHey>']], let_it=False)
    if delete:
        await msg.sendMessage(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('headers reset {重置headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    reset = target.config_headers('', let_it=None)
    if reset:
        await msg.sendMessage(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('prefix set <prefix> {设置查询自动添加前缀}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    prefix = msg.parsed_msg['<prefix>']
    set_prefix = target.set_prefix(prefix)
    if set_prefix:
        await msg.sendMessage(f'成功更新请求时所使用的前缀：{prefix}')


@wiki.handle('prefix reset {重置查询自动添加的前缀}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    set_prefix = target.del_prefix()
    if set_prefix:
        await msg.sendMessage(f'成功重置请求时所使用的前缀。')


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
        if req['trust']:
            res = Audit(api).add_to_AllowList(op)
            list_name = '白'
        else:
            res = Audit(api).add_to_BlockList(op)
            list_name = '黑'
        if not res:
            await msg.sendMessage(f'失败，此wiki已经存在于{list_name}名单中：' + api)
        else:
            await msg.sendMessage(f'成功加入{list_name}名单：' + api)
    else:
        result = '错误：无法添加此Wiki。' + ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.sendMessage(result)


@aud.handle(['distrust <apiLink>', 'unblock <apiLink>'])
async def _(msg: MessageSession):
    req = msg.parsed_msg
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check:
        api = check.value.api
        if req['distrust']:
            res = Audit(api).remove_from_AllowList()
            list_name = '白'
        else:
            res = Audit(api).remove_from_BlockList()
            list_name = '黑'
        if not res:
            await msg.sendMessage(f'失败，此wiki不存在于{list_name}名单中：' + api)
        else:
            await msg.sendMessage(f'成功从{list_name}名单删除：' + api)
    else:
        result = '错误：无法查询此Wiki。' + ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.sendMessage(result)


@aud.handle('query <apiLink>')
async def _(msg: MessageSession):
    req = msg.parsed_msg
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check:
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
            await msg.sendMessage('\n'.join(msg_list))
        else:
            await msg.sendMessage(api + '不存在于任何名单。')
    else:
        result = '错误：无法查询此Wiki。' + ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.sendMessage(result)


@aud.handle('list')
async def _(msg: MessageSession):
    allow_list = Audit.get_allow_list()
    block_list = Audit.get_block_list()
    legacy = True
    if msg.Feature.image:
        send_msgs = []
        allow_columns = [[x[0], x[1]] for x in allow_list]
        if allow_columns:
            allow_table = ImageTable(data=allow_columns, headers=['APILink', 'Operator'])
            if allow_table:
                allow_image = await image_table_render(allow_table)
                if allow_image:
                    send_msgs.append(Plain('现有白名单：'))
                    send_msgs.append(Image(allow_image))
        block_columns = [[x[0], x[1]] for x in block_list]
        if block_columns:
            block_table = ImageTable(data=block_columns, headers=['APILink', 'Operator'])
            if block_table:
                block_image = await image_table_render(block_table)
                if block_image:
                    send_msgs.append(Plain('现有黑名单：'))
                    send_msgs.append(Image(block_image))
        if send_msgs:
            await msg.sendMessage(send_msgs)
            legacy = False
    if legacy:
        wikis = []
        wikis.append('现有白名单：')
        for al in allow_list:
            wikis.append(f'{al[0]}（by {al[1]}）')
        wikis.append('现有黑名单：')
        for bl in block_list:
            wikis.append(f'{bl[0]}（by {bl[1]}）')
        await msg.sendMessage('\n'.join(wikis))


on_option('wiki_fandom_addon', desc='为Fandom定制的查询附加功能。', developers=['OasisAkari'])

wiki_inline = on_regex('wiki_inline',
                       desc='解析消息中带有的[[]]或{{}}字符串自动查询Wiki，如[[海晶石]]',
                       alias='wiki_regex', developers=['OasisAkari'])


@wiki_inline.handle(r'\[\[(.*?)]]', mode='A', flags=re.I)
async def _(msg: MessageSession):
    query_list = []
    for x in msg.matched_msg:
        if x != '' and x not in query_list and x[0] != '#':
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list)


@wiki_inline.handle(r'\{\{(.*?)}}', mode='A', flags=re.I)
async def _(msg: MessageSession):
    query_list = []
    print(msg.matched_msg)
    for x in msg.matched_msg:
        if x != '' and x not in query_list and x[0] != '#' and x.find("{") == -1:
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list, template=True)


@wiki_inline.handle(r'≺(.*?)≻|⧼(.*?)⧽', mode='A', flags=re.I, show_typing=False)
async def _(msg: MessageSession):
    query_list = []
    print(msg.matched_msg)
    for x in msg.matched_msg:
        for y in x:
            if y != '' and y not in query_list and y[0] != '#':
                query_list.append(y)
    if query_list:
        await query_pages(msg, query_list, mediawiki=True)


async def query_pages(msg: MessageSession, title: Union[str, list, tuple],
                      template=False, mediawiki=False, useprefix=True):
    target = WikiTargetInfo(msg)
    start_wiki = target.get_start_wiki()
    interwiki_list = target.get_interwikis()
    headers = target.get_headers()
    prefix = target.get_prefix()
    enabled_fandom_addon = BotDBUtil.Module(msg).check_target_enabled_module('wiki_fandom_addon')
    if start_wiki is None:
        await msg.sendMessage('没有指定起始Wiki，已默认指定为中文Minecraft Wiki，发送~wiki set <域名>来设定自定义起始Wiki。'
                              '\n例子：~wiki set https://minecraft.fandom.com/zh/wiki/')
        start_wiki = 'https://minecraft.fandom.com/zh/api.php'
    if isinstance(title, str):
        title = [title]
    if len(title) > 15:
        raise AbuseWarning('一次性查询的页面超出15个。')
    query_task = {start_wiki: {'query': [], 'iw_prefix': ''}}
    for t in title:
        if prefix is not None and useprefix:
            t = prefix + t
        if t[0] == ':':
            if len(t) > 1:
                query_task[start_wiki]['query'].append(t[1:])
        else:
            match_interwiki = re.match(r'^(.*?):(.*)', t)
            if match_interwiki:
                g1 = match_interwiki.group(1)
                g2 = match_interwiki.group(2)
                if g1 in interwiki_list:
                    interwiki_url = interwiki_list[g1]
                    if interwiki_url not in query_task:
                        query_task[interwiki_url] = {'query': [], 'iw_prefix': g1}
                    query_task[interwiki_url]['query'].append(g2)
                elif g1 == 'w' and enabled_fandom_addon:
                    if match_interwiki := re.match(r'(.*?):(.*)', match_interwiki.group(2)):
                        if match_interwiki.group(1) == 'c':
                            if match_interwiki := re.match(r'(.*?):(.*)', match_interwiki.group(2)):
                                interwiki_split = match_interwiki.group(1).split('.')
                                if len(interwiki_split) == 2:
                                    get_link = f'https://{interwiki_split[1]}.fandom.com/api.php'
                                    find = interwiki_split[0] + ':' + match_interwiki.group(2)
                                    iw = 'w:c:' + interwiki_split[0]
                                else:
                                    get_link = f'https://{match_interwiki.group(1)}.fandom.com/api.php'
                                    find = match_interwiki.group(2)
                                    iw = 'w:c:' + match_interwiki.group(1)
                                if get_link not in query_task:
                                    query_task[get_link] = {'query': [], 'iw_prefix': iw}
                                query_task[get_link]['query'].append(find)
                            else:
                                query_task[start_wiki]['query'].append(t)
                        else:
                            query_task[start_wiki]['query'].append(t)
                    else:
                        query_task[start_wiki]['query'].append(t)
                else:
                    query_task[start_wiki]['query'].append(t)
            else:
                query_task[start_wiki]['query'].append(t)
    print(query_task)
    msg_list = []
    wait_msg_list = []
    wait_list = []
    web_render_list = []
    for q in query_task:
        current_task = query_task[q]
        ready_for_query_pages = current_task['query']
        iw_prefix = (current_task['iw_prefix'] + ':') if current_task['iw_prefix'] != '' else ''
        try:
            tasks = []
            for rd in ready_for_query_pages:
                if rd == '随机页面':
                    tasks.append(asyncio.create_task(WikiLib(q, headers).random_page()))
                else:
                    if template:
                        rd = f'Template:{rd}'
                    if mediawiki:
                        rd = f'MediaWiki:{rd}'
                    tasks.append(asyncio.ensure_future(WikiLib(q, headers).parse_page_info(rd)))
            query = await asyncio.gather(*tasks)
            for result in query:
                print(result.__dict__)
                r: PageInfo = result
                iw_prefix = iw_prefix
                display_title = None
                display_before_title = None
                if r.title is not None:
                    display_title = iw_prefix + r.title
                if r.before_title is not None:
                    display_before_title = iw_prefix + r.before_title
                if r.status:
                    plain_slice = []
                    if display_before_title is not None and display_before_title != display_title:
                        if r.before_page_property == 'template' and r.page_property == 'page':
                            plain_slice.append(f'（[{display_before_title}]不存在，已自动重定向至[{display_title}]）')
                        else:
                            plain_slice.append(f'（重定向[{display_before_title}] -> [{display_title}]）')
                    if r.link is not None:
                        plain_slice.append(r.link)
                    if r.desc is not None and r.desc != '':
                        plain_slice.append(r.desc)
                    if plain_slice:
                        msg_list.append(Plain('\n'.join(plain_slice)))
                    if r.file is not None:
                        dl = await download_to_cache(r.file)
                        guess_type = filetype.guess(dl)
                        if guess_type is not None:
                            if guess_type.extension in ["png", "gif", "jpg", "jpeg", "webp", "bmp", "ico"]:
                                if msg.Feature.image:
                                    msg_list.append(Image(dl))
                            elif guess_type.extension in ["oga", "ogg", "flac", "mp3", "wav"]:
                                if msg.Feature.voice:
                                    msg_list.append(Voice(dl))
                    else:
                        if msg.Feature.image and r.link is not None:
                            web_render_list.append({r.link: r.info.realurl})
                else:
                    plain_slice = []
                    wait_plain_slice = []
                    if display_title is not None and display_before_title is not None:
                        wait_plain_slice.append(f'提示：[{display_before_title}]不存在，您是否想要找的是[{display_title}]？')
                        wait_list.append(display_title)
                    elif r.before_title is not None:
                        plain_slice.append(f'提示：找不到[{display_before_title}]。')
                    if r.desc is not None and r.desc != '':
                        plain_slice.append(r.desc)
                    if r.invalid_namespace and r.before_title is not None:
                        s = r.before_title.split(":")
                        if len(s) > 1:
                            wait_plain_slice.append(f'此Wiki上没有名为{s[0]}的命名空间，请检查拼写后再试。')
                    if plain_slice:
                        msg_list.append(Plain('\n'.join(plain_slice)))
                    if wait_plain_slice:
                        wait_msg_list.append(Plain('\n'.join(wait_plain_slice)))
        except WhatAreUDoingError:
            raise AbuseWarning('使机器人重定向页面的次数过多。')
        except InvalidWikiError as e:
            await msg.sendMessage(f'发生错误：' + str(e))
    if msg_list:
        await msg.sendMessage(msg_list)
    if web_render_list and msg.Feature.image:
        infobox_msg_list = []
        for i in web_render_list:
            for ii in i:
                get_infobox = await get_infobox_pic(i[ii], ii, headers)
                if get_infobox:
                    infobox_msg_list.append(Image(get_infobox))
        if infobox_msg_list:
            await msg.sendMessage(infobox_msg_list, quote=False)
    if wait_msg_list:
        confirm = await msg.waitConfirm(wait_msg_list)
        if confirm and wait_list:
            await query_pages(msg, wait_list, useprefix=False)


rc_ = on_command('rc', desc='获取默认wiki的最近更改', developers=['OasisAkari'])


@rc_.handle()
async def rc_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.sendMessage('未设置起始wiki。')
    legacy = True
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        try:
            nodelist = await rc_qq(start_wiki)
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            traceback.print_exc()
            await msg.sendMessage('无法发送转发消息，已自动回滚至传统样式。')
            legacy = True
    if legacy:
        res = await rc(start_wiki)
        await msg.sendMessage(res)


a = on_command('ab', desc='获取默认wiki的最近滥用日志', developers=['OasisAkari'])


@a.handle()
async def ab_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.sendMessage('未设置起始wiki。')
    legacy = True
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        try:
            nodelist = await ab_qq(start_wiki)
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            traceback.print_exc()
            await msg.sendMessage('无法发送转发消息，已自动回滚至传统样式。')
            legacy = True
    if legacy:
        res = await ab(start_wiki)
        await msg.sendMessage(res)


n = on_command('newbie', desc='获取默认wiki的新用户', developers=['OasisAkari'])


@n.handle()
async def newbie_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.sendMessage('未设置起始wiki。')
    res = await newbie(start_wiki)
    await msg.sendMessage(res)
