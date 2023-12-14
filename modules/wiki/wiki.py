import asyncio
import re
from typing import Union

import filetype

from core.builtins import Bot, Plain, Image, Voice, Url, confirm_command
from core.utils.image_table import image_table_render, ImageTable
from core.component import module
from core.exceptions import AbuseWarning
from core.logger import Logger
from core.utils.http import download_to_cache
from modules.wiki.utils.dbutils import WikiTargetInfo
from modules.wiki.utils.screenshot_image import generate_screenshot_v1, generate_screenshot_v2
from modules.wiki.utils.wikilib import WikiLib, WhatAreUDoingError, PageInfo, InvalidWikiError, QueryInfo

generate_screenshot_v2_blocklist = ['https://mzh.moegirl.org.cn', 'https://zh.moegirl.org.cn']
special_namespace = ['special', '特殊']
random_title = ['random', '随机页面', '隨機頁面']

wiki = module('wiki',
              alias={'wiki_start_site': 'wiki set',
                     'interwiki': 'wiki iw'},
              recommend_modules='wiki_inline',
              developers=['OasisAkari'])


@wiki.command('<PageName> [-l <lang>] {{wiki.help}}',
              options_desc={'-l': '{wiki.help.option.l}'})
async def _(msg: Bot.MessageSession):
    get_lang = msg.parsed_msg.get('-l', False)
    if get_lang:
        lang = get_lang['<lang>']
    else:
        lang = None
    await query_pages(msg, msg.parsed_msg['<PageName>'], lang=lang)


@wiki.command('id <PageID> {{wiki.help.id}}')
async def _(msg: Bot.MessageSession):
    page_id: str = msg.parsed_msg['<PageID>']
    iw = None
    if match_iw := re.match(r'(.*?):(.*)', page_id):
        iw = match_iw.group(1)
        page_id = match_iw.group(2)
    if not page_id.isdigit():
        await msg.finish(msg.locale.t('wiki.message.id.error'))
    Logger.debug(msg.parsed_msg)
    await query_pages(msg, pageid=page_id, iw=iw)


async def query_pages(session: Union[Bot.MessageSession, QueryInfo], title: Union[str, list, tuple] = None,
                      pageid: str = None, iw: str = None, lang: str = None,
                      template=False, mediawiki=False, use_prefix=True, inline_mode=False, preset_message=None):
    if isinstance(session, Bot.MessageSession):
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
        interwiki_list = {}
        headers = session.headers
        prefix = session.prefix
        enabled_fandom_addon = False
    else:
        raise TypeError('session must be Bot.MessageSession or QueryInfo.')

    if start_wiki is None:
        if isinstance(session, Bot.MessageSession):
            await session.send_message(session.locale.t('wiki.message.set.default', prefix=session.prefixes[0]))
        start_wiki = 'https://zh.minecraft.wiki/api.php'
    if lang in interwiki_list:
        start_wiki = interwiki_list[lang]
        lang = None
    if title is not None:
        if isinstance(title, str):
            title = [title]
        if len(title) > 15:
            raise AbuseWarning(session.locale.t('tos.reason.wiki_abuse'))
        query_task = {start_wiki: {'query': [], 'iw_prefix': ''}}
        for t in title:
            if prefix is not None and use_prefix:
                t = prefix + t
            if not t:
                continue
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
            if iw in interwiki_list:
                query_task = {interwiki_list[iw]: {
                    'queryid': [pageid], 'iw_prefix': iw}}
            else:
                get_wiki_info = WikiLib(start_wiki)
                await get_wiki_info.fixup_wiki_info()
                if iw in get_wiki_info.wiki_info.interwiki:
                    query_task = {get_wiki_info.wiki_info.interwiki[iw]: {
                        'queryid': [pageid], 'iw_prefix': iw}}
                else:
                    raise ValueError(f'iw_prefix "{iw}" not found.')
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
                if rd.split(":")[0].lower() in special_namespace and rd.split(":")[1].lower() in random_title:
                    tasks.append(asyncio.create_task(
                        WikiLib(q, headers, locale=session.locale.locale).random_page()))
                else:
                    if template:
                        rd = f'Template:{rd}'
                    if mediawiki:
                        rd = f'MediaWiki:{rd}'
                    tasks.append(asyncio.ensure_future(
                        WikiLib(q, headers, locale=session.locale.locale)
                        .parse_page_info(title=rd, inline=inline_mode, lang=lang)))
            for rdp in ready_for_query_ids:
                tasks.append(asyncio.ensure_future(
                    WikiLib(q, headers, locale=session.locale.locale)
                    .parse_page_info(pageid=rdp, inline=inline_mode, lang=lang)))
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
                            plain_slice.append(session.locale.t('wiki.message.redirect.template_to_page',
                                                                title=display_before_title,
                                                                redirected_title=display_title))
                        else:
                            plain_slice.append(session.locale.t('wiki.message.redirect', title=display_before_title,
                                                                redirected_title=display_title))
                    if (r.link is not None and r.selected_section is not None and r.info.in_allowlist and
                            not r.invalid_section):
                        render_section_list.append(
                            {r.link: {'url': r.info.realurl, 'section': r.selected_section,
                                      'in_allowlist': r.info.in_allowlist}})
                        plain_slice.append(session.locale.t("wiki.message.section.rendering"))
                    else:
                        if r.desc is not None and r.desc != '':
                            plain_slice.append(r.desc)

                    if r.link is not None:
                        plain_slice.append(
                            str(Url(r.link, use_mm=not r.info.in_allowlist)))

                    if r.file is not None:
                        dl_list.append(r.file)
                        plain_slice.append(session.locale.t('wiki.message.flies') + r.file)
                    else:
                        if r.link is not None and r.selected_section is None:
                            render_infobox_list.append(
                                {r.link: {'url': r.info.realurl, 'in_allowlist': r.info.in_allowlist,
                                          'content_mode': r.has_template_doc or r.title.split(':')[0] in ['User'] or
                                          (r.templates is not None and
                                           ('Template:Disambiguation' in r.templates or
                                            'Template:Version disambiguation' in r.templates))}})
                    if plain_slice:
                        msg_list.append(Plain('\n'.join(plain_slice)))
                    if r.invalid_section and r.info.in_allowlist:
                        if isinstance(session, Bot.MessageSession):

                            if session.Feature.image:
                                i_msg_lst = []
                                session_data = [[str(i + 1), r.sections[i]] for i in range(len(r.sections))]
                                i_msg_lst.append(Plain(session.locale.t('wiki.message.invalid_section')))
                                i_msg_lst.append(Image(await
                                                       image_table_render(
                                                           ImageTable(session_data,
                                                                      ['ID',
                                                                       session.locale.t('wiki.message.section')]))))

                                async def _callback(msg: Bot.MessageSession):
                                    display = msg.as_display(text_only=True)
                                    if display.isdigit():
                                        display = int(display)
                                        if display <= len(r.sections):
                                            r.selected_section = display - 1
                                            await query_pages(session, title=r.title + '#' + r.sections[display - 1])

                                await session.send_message(i_msg_lst, callback=_callback)
                            else:
                                msg_list.append(Plain(session.locale.t('wiki.message.invalid_section.prompt')))
                else:
                    plain_slice = []
                    wait_plain_slice = []
                    if display_title is not None and display_before_title is not None:
                        if isinstance(session, Bot.MessageSession) and session.Feature.wait:
                            if not session.options.get('wiki_redlink', False):
                                if len(r.possible_research_title) > 1:
                                    wait_plain_slice.append(session.locale.t('wiki.message.not_found.autofix.choice',
                                                                             title=display_before_title))
                                    pi = 0
                                    for p in r.possible_research_title:
                                        pi += 1
                                        wait_plain_slice.append(
                                            f'{pi}. {p}')
                                    wait_plain_slice.append(
                                        session.locale.t('wiki.message.not_found.autofix.choice.prompt', number=str(
                                            r.possible_research_title.index(display_title) + 1)))
                                    wait_possible_list.append({display_before_title: {display_title:
                                                                                      r.possible_research_title}})
                                    wait_plain_slice.append(session.locale.t("message.wait.confirm.prompt.type2"))
                                else:
                                    wait_plain_slice.append(session.locale.t('wiki.message.not_found.autofix.confirm',
                                                                             title=display_before_title,
                                                                             redirected_title=display_title))
                                    wait_plain_slice.append(session.locale.t("message.wait.confirm.prompt.type1"))
                            else:
                                if r.edit_link is not None:
                                    plain_slice.append(r.edit_link + session.locale.t('wiki.message.redlink.not_found'))
                                else:
                                    plain_slice.append(session.locale.t('wiki.message.redlink.not_found.uneditable',
                                                                        title=display_before_title))
                        else:
                            wait_plain_slice.append(
                                session.locale.t('wiki.message.not_found.autofix', title=display_before_title,
                                                 redirected_title=display_title))
                        if len(r.possible_research_title) == 1:
                            wait_list.append({display_title: display_before_title})
                    elif r.before_title is not None:
                        plain_slice.append(session.locale.t('wiki.message.not_found', title=display_before_title))
                    elif r.id != -1:
                        plain_slice.append(session.locale.t('wiki.message.id.not_found', id=str(r.id)))
                    if r.desc is not None and r.desc != '':
                        plain_slice.append(r.desc)
                    if r.invalid_namespace and r.before_title is not None:
                        plain_slice.append(
                            session.locale.t('wiki.message.invalid_namespace', namespace=r.invalid_namespace))
                    if r.before_page_property == 'template':
                        if r.before_title.split(':')[1].isupper():
                            plain_slice.append(session.locale.t('wiki.message.magic_word'))
                    if plain_slice:
                        msg_list.append(Plain('\n'.join(plain_slice)))
                    if wait_plain_slice:
                        wait_msg_list.append(
                            Plain('\n'.join(wait_plain_slice)))
        except WhatAreUDoingError:
            raise AbuseWarning(session.locale.t('tos.reason.too_many_redirects'))
        except InvalidWikiError as e:
            if isinstance(session, Bot.MessageSession):
                await session.send_message(session.locale.t('error') + str(e))
            else:
                msg_list.append(Plain(session.locale.t('error') + str(e)))
    if isinstance(session, Bot.MessageSession):
        if msg_list:
            if all([not render_infobox_list, not render_section_list,
                    not dl_list, not wait_list, not wait_possible_list]):
                await session.finish(msg_list)
            else:
                await session.send_message(msg_list)

        async def infobox():
            if render_infobox_list and session.Feature.image:
                infobox_msg_list = []
                for i in render_infobox_list:
                    for ii in i:
                        Logger.info(i[ii]['url'])
                        if i[ii]['url'] not in generate_screenshot_v2_blocklist:

                            get_infobox = await generate_screenshot_v2(ii, allow_special_page=i[ii]['in_allowlist'],
                                                                       content_mode=i[ii]['content_mode'])
                            if get_infobox:
                                infobox_msg_list.append(Image(get_infobox))
                        else:
                            get_infobox = await generate_screenshot_v1(i[ii]['url'], ii, headers,
                                                                       allow_special_page=i[ii]['in_allowlist'])
                            if get_infobox:
                                infobox_msg_list.append(Image(get_infobox))
                if infobox_msg_list:
                    await session.send_message(infobox_msg_list, quote=False)

        async def section():
            if render_section_list and session.Feature.image:
                section_msg_list = []
                for i in render_section_list:
                    for ii in i:
                        if i[ii]['in_allowlist']:
                            if i[ii]['url'] not in generate_screenshot_v2_blocklist:
                                get_section = await generate_screenshot_v2(ii, section=i[ii]['section'])
                                if get_section:
                                    section_msg_list.append(Image(get_section))
                                else:
                                    section_msg_list.append(Plain(
                                        session.locale.t("wiki.message.error.unable_to_render_section")))
                            else:
                                get_section = await generate_screenshot_v1(i[ii]['url'], ii, headers,
                                                                           section=i[ii]['section'])
                                if get_section:
                                    section_msg_list.append(Image(get_section))
                                else:
                                    section_msg_list.append(Plain(
                                        session.locale.t("wiki.message.error.unable_to_render_section")))
                if section_msg_list:
                    await session.send_message(section_msg_list, quote=False)

        async def image_and_voice():
            if dl_list:
                for f in dl_list:
                    dl = await download_to_cache(f)
                    guess_type = filetype.guess(dl)
                    if guess_type is not None:
                        if guess_type.extension in ["png", "gif", "jpg", "jpeg", "webp", "bmp", "ico"]:
                            if session.Feature.image:
                                await session.send_message(Image(dl), quote=False)
                        elif guess_type.extension in ["oga", "ogg", "flac", "mp3", "wav"]:
                            if session.Feature.voice:
                                await session.send_message(Voice(dl), quote=False)

        async def wait_confirm():
            if wait_msg_list and session.Feature.wait:
                confirm = await session.wait_next_message(wait_msg_list, delete=True, append_instruction=False)
                auto_index = False
                index = 0
                if confirm.as_display(text_only=True) in confirm_command:
                    auto_index = True
                elif confirm.as_display(text_only=True).isdigit():
                    index = int(confirm.as_display()) - 1
                else:
                    return
                preset_message = []
                wait_list_ = []
                for w in wait_list:
                    for wd in w:
                        preset_message.append(
                            session.locale.t('wiki.message.redirect.autofix', title=w[wd], redirected_title=wd))
                        wait_list_.append(wd)
                if auto_index:
                    for wp in wait_possible_list:
                        for wpk in wp:
                            keys = list(wp[wpk].keys())
                            preset_message.append(
                                session.locale.t('wiki.message.redirect.autofix', title=wpk, redirected_title=keys[0]))
                            wait_list_.append(keys[0])
                else:
                    for wp in wait_possible_list:
                        for wpk in wp:
                            keys = list(wp[wpk].keys())
                            if len(wp[wpk][keys[0]]) > index:
                                preset_message.append(session.locale.t('wiki.message.redirect.autofix', title=wpk,
                                                                       redirected_title=wp[wpk][keys[0]][index]))
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
