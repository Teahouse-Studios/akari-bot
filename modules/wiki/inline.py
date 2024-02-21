import asyncio
import re
import urllib.parse

import filetype

from core.builtins import Bot, Plain, Image, Voice
from core.component import module
from core.dirty_check import check
from core.logger import Logger
from core.utils.http import download_to_cache
from core.utils.image import svg_render
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.utils.dbutils import WikiTargetInfo
from modules.wiki.utils.screenshot_image import generate_screenshot_v1, generate_screenshot_v2
from modules.wiki.utils.wikilib import WikiLib
from .wiki import query_pages, generate_screenshot_v2_blocklist, web_render

wiki_inline = module('wiki_inline',
                     desc='{wiki.help.wiki_inline.desc}', recommend_modules=['wiki'],
                     alias='wiki_regex', developers=['OasisAkari'])


@wiki_inline.regex(re.compile(r'\[\[(.*?)]]', flags=re.I), mode='A',
                   desc="{wiki.help.wiki_inline.page}")
async def _(msg: Bot.MessageSession):
    query_list = []
    for x in msg.matched_msg:
        if x != '' and x not in query_list and x[0] != '#':
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list, inline_mode=True)


@wiki_inline.regex(re.compile(r'\{\{(.*?)}}', flags=re.I), mode='A',
                   desc='{wiki.help.wiki_inline.template}')
async def _(msg: Bot.MessageSession):
    query_list = []
    for x in msg.matched_msg:
        if x != '' and x not in query_list and x[0] != '#' and x.find("{") == -1:
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list, template=True, inline_mode=True)


@wiki_inline.regex(re.compile(r'≺(.*?)≻|⧼(.*?)⧽', flags=re.I), mode='A', show_typing=False,
                   desc='{wiki.help.wiki_inline.mediawiki}')
async def _(msg: Bot.MessageSession):
    query_list = []
    for x in msg.matched_msg:
        for y in x:
            if y != '' and y not in query_list and y[0] != '#':
                query_list.append(y)
    if query_list:
        await query_pages(msg, query_list, mediawiki=True, inline_mode=True)


@wiki_inline.regex(re.compile(
    r'(https?://[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,4}\b[-a-zA-Z0-9@:%_+.~#?&/=]*)', flags=re.I),
    mode='A', show_typing=False, logging=False,
    desc='{wiki.help.wiki_inline.url}')
async def _(msg: Bot.MessageSession):
    match_msg = msg.matched_msg

    def check_svg(file_path):
        try:
            with open(file_path, 'r') as file:
                check = file.read(1024)
                return '<svg' in check
        except Exception:
            return False

    async def bgtask():
        query_list = []
        target = WikiTargetInfo(msg)
        headers = target.get_headers()
        for x in match_msg:
            wiki_ = WikiLib(x)
            if check_from_database := await wiki_.check_wiki_info_from_database_cache():
                if check_from_database.available:
                    check_from_api = await wiki_.check_wiki_available()
                    if check_from_api.available:
                        query_list.append({x: check_from_api.value})
        if query_list:
            Logger.info(query_list)
            for q in query_list:
                img_send = False
                for qq in q:
                    wiki_ = WikiLib(qq)
                    articlepath = q[qq].articlepath.replace('$1', '(.*)')
                    get_id = re.sub(r'.*curid=(\d+)', '\\1', qq)
                    get_title = re.sub(r'' + articlepath, '\\1', qq)
                    get_page = None
                    if get_id.isdigit():
                        get_page = await wiki_.parse_page_info(pageid=int(get_id))
                        if not q[qq].in_allowlist:
                            for result in await check(get_page.title):
                                if not result['status']:
                                    return
                    elif get_title != '':
                        title = urllib.parse.unquote(get_title)
                        if not q[qq].in_allowlist:
                            for result in await check(title):
                                if not result['status']:
                                    return
                        get_page = await wiki_.parse_page_info(title)
                    if get_page:
                        if get_page.status and get_page.file:
                            dl = await download_to_cache(get_page.file)
                            guess_type = filetype.guess(dl)
                            if guess_type:
                                if guess_type.extension in ["png", "gif", "jpg", "jpeg", "webp", "bmp", "ico"]:
                                    if msg.Feature.image:
                                        await msg.send_message(
                                            [Plain(msg.locale.t('wiki.message.wiki_inline.flies', file=get_page.file)),
                                             Image(dl)],
                                            quote=False)
                                        img_send = True
                                elif guess_type.extension in ["oga", "ogg", "flac", "mp3", "wav"]:
                                    if msg.Feature.voice:
                                        await msg.send_message(
                                            [Plain(msg.locale.t('wiki.message.wiki_inline.flies', file=get_page.file)),
                                             Voice(dl)],
                                            quote=False)
                            elif check_svg:
                                rd = await svg_render(dl)
                                if msg.Feature.image and rd:
                                    await msg.send_message(
                                        [Plain(msg.locale.t('wiki.message.wiki_inline.flies', file=get_page.file)),
                                         Image(rd)],
                                        quote=False)

                        if msg.Feature.image:
                            if get_page.status and wiki_.wiki_info.in_allowlist:
                                if wiki_.wiki_info.realurl not in generate_screenshot_v2_blocklist:
                                    get_infobox = await generate_screenshot_v2(qq,
                                                                               allow_special_page=q[qq].in_allowlist,
                                                                               content_mode=get_page.has_template_doc or
                                                                               get_page.title.split(':')[
                                                                                   0] in [
                                                                                   'User'] or
                                                                               (
                                                                                   'Template:Disambiguation' in get_page.templates
                                                                                   or 'Template:Version disambiguation' in get_page.templates))
                                    if get_infobox:
                                        await msg.send_message(Image(get_infobox), quote=False)
                                else:
                                    get_infobox = await generate_screenshot_v1(q[qq].realurl, qq, headers)
                                    if get_infobox:
                                        await msg.send_message(Image(get_infobox), quote=False)
                            if get_page.invalid_section and wiki_.wiki_info.in_allowlist and web_render:
                                i_msg_lst = []
                                session_data = [[str(i + 1), get_page.sections[i]] for i in
                                                range(len(get_page.sections))]
                                i_msg_lst.append(Plain(msg.locale.t('wiki.message.invalid_section')))
                                i_msg_lst.append(Image(await
                                                       image_table_render(
                                                           ImageTable(session_data,
                                                                      ['ID',
                                                                       msg.locale.t('wiki.message.section')]))))

                                async def _callback(msg: Bot.MessageSession):
                                    display = msg.as_display(text_only=True)
                                    if display.isdigit():
                                        display = int(display)
                                        if display <= len(get_page.sections):
                                            get_page.selected_section = display - 1
                                            await query_pages(msg, title=get_page.title + '#' +
                                                              get_page.sections[display - 1])

                                await msg.send_message(i_msg_lst, callback=_callback)
                if len(query_list) == 1 and img_send:
                    return
                if msg.Feature.image:
                    for qq in q:
                        section_ = []
                        quote_code = False
                        page_name = urllib.parse.unquote(qq)
                        for qs in page_name:
                            if qs == '#':
                                quote_code = True
                            if qs == '?':
                                quote_code = False
                            if quote_code:
                                section_.append(qs)
                        if section_:
                            s = urllib.parse.unquote(''.join(section_)[1:])
                            if q[qq].realurl and q[qq].in_allowlist:
                                if q[qq].realurl in generate_screenshot_v2_blocklist:
                                    get_section = await generate_screenshot_v1(q[qq].realurl, qq, headers, section=s)
                                else:
                                    get_section = await generate_screenshot_v2(qq, section=s)
                                if get_section:
                                    await msg.send_message(Image(get_section))

    await asyncio.create_task(bgtask())
