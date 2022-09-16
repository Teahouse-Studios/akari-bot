import asyncio
import re
from typing import Union

import filetype

from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Plain, Image, Voice, Url, confirm_command
from core.exceptions import AbuseWarning
from core.logger import Logger
from core.utils import download_to_cache
from modules.wiki.utils.dbutils import WikiTargetInfo
from modules.wiki.utils.screenshot_image import get_pic
from modules.wiki.utils.wikilib import WikiLib, WhatAreUDoingError, PageInfo, InvalidWikiError, QueryInfo

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

                    if r.file is not None:
                        dl_list.append(r.file)
                        plain_slice.append('此页面包含以下文件：\n' + r.file)
                    else:
                        if r.link is not None and r.section is None:
                            render_infobox_list.append(
                                {r.link: {'url': r.info.realurl, 'in_allowlist': r.info.in_allowlist}})
                        elif r.link is not None and r.section is not None and r.info.in_allowlist:
                            render_section_list.append(
                                {r.link: {'url': r.info.realurl, 'section': r.section,
                                          'in_allowlist': r.info.in_allowlist}})
                    if plain_slice:
                        msg_list.append(Plain('\n'.join(plain_slice)))
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
                                wait_plain_slice.append(f'请直接发送指定序号获取对应内容，若回复“是”，'
                                                        f'则默认选择'
                                                        f'{str(r.possible_research_title.index(display_title) + 1)}'
                                                        f'号内容，发送其他内容则代表取消获取。')
                                wait_possible_list.append({display_before_title: {display_title:
                                                                                      r.possible_research_title}})
                            else:
                                wait_plain_slice.append(
                                    f'提示：[{display_before_title}]不存在，您是否想要找的是[{display_title}]？\n'
                                    f'（请直接发送“是”字来确认，发送其他内容则代表取消获取。）')
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
            if all(
                [not render_infobox_list, not render_section_list, not dl_list, not wait_list, not wait_possible_list]):
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
