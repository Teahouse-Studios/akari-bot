import asyncio
import re
import urllib.parse

import filetype

from core.builtins import Bot, I18NContext, Image, Voice
from core.component import module
from core.constants.info import Info
from core.dirty_check import check
from core.logger import Logger
from core.utils.http import download
from core.utils.image import svg_render
from core.utils.image_table import image_table_render, ImageTable
from core.utils.text import isint
from modules.wiki.database.models import WikiTargetInfo
from modules.wiki.utils.screenshot_image import (
    generate_screenshot_v1,
    generate_screenshot_v2,
)
from modules.wiki.utils.wikilib import WikiLib
from .wiki import query_pages, generate_screenshot_v2_blocklist

wiki_inline = module(
    "wiki_inline",
    desc="{wiki.help.wiki_inline.desc}",
    doc=True,
    recommend_modules=["wiki"],
    alias="wiki_regex",
    developers=["OasisAkari"],
)


@wiki_inline.regex(r"\[\[(.*?)\]\]", flags=re.I, mode="A", desc="{wiki.help.wiki_inline.page}")
async def _(msg: Bot.MessageSession):
    query_list = []
    for x in msg.matched_msg:
        if x != "" and x not in query_list and x[0] != "#":
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list[:5], inline_mode=True)


@wiki_inline.regex(r"\{\{(.*?)\}\}", flags=re.I, mode="A", desc="{wiki.help.wiki_inline.template}")
async def _(msg: Bot.MessageSession):
    query_list = []
    for x in msg.matched_msg:
        if x != "" and x not in query_list and x[0] != "#" and x.find("{") == -1:
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list[:5], template=True, inline_mode=True)


@wiki_inline.regex(r"≺(.*?)≻|⧼(.*?)⧽",
                   flags=re.I,
                   mode="A",
                   show_typing=False,
                   desc="{wiki.help.wiki_inline.mediawiki}")
async def _(msg: Bot.MessageSession):
    query_list = []
    for x in msg.matched_msg:
        for y in x:
            if y != "" and y not in query_list and y[0] != "#":
                query_list.append(y)
    if query_list:
        await query_pages(msg, query_list[:5], mediawiki=True, inline_mode=True)


@wiki_inline.regex(r"(https?://[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,4}\b[-a-zA-Z0-9@:%_+.~#?&/=]*)",
                   flags=re.I,
                   mode="A",
                   show_typing=False,
                   logging=False,
                   desc="{wiki.help.wiki_inline.url}")
async def _(msg: Bot.MessageSession):
    match_msg = msg.matched_msg

    def check_svg(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                check = file.read(1024)
                return "<svg" in check
        except Exception:
            return False

    async def bgtask():
        query_list = []
        target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
        headers = target.headers
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
                    articlepath = q[qq].articlepath.replace("$1", "(.*)")
                    get_id = re.sub(r".*curid=(\d+)", "\\1", qq)
                    get_title = re.sub(r"" + articlepath, "\\1", qq)
                    get_page = None
                    if isint(get_id):
                        get_page = await wiki_.parse_page_info(pageid=int(get_id))
                        if not q[qq].in_allowlist and Info.use_url_manager:
                            for result in await check(get_page.title):
                                if not result["status"]:
                                    return
                    elif get_title != "":
                        title = urllib.parse.unquote(get_title)
                        if not q[qq].in_allowlist and Info.use_url_manager:
                            for result in await check(title):
                                if not result["status"]:
                                    return
                        get_page = await wiki_.parse_page_info(title)
                    if get_page:
                        if get_page.status and get_page.file:
                            dl = await download(get_page.file)
                            guess_type = filetype.guess(dl)
                            if guess_type:
                                if guess_type.extension in [
                                    "png",
                                    "gif",
                                    "jpg",
                                    "jpeg",
                                    "webp",
                                    "bmp",
                                    "ico",
                                ]:
                                    if msg.Feature.image:
                                        await msg.send_message(
                                            [
                                                I18NContext(
                                                    "wiki.message.wiki_inline.flies",
                                                    file=get_page.file,
                                                ),
                                                Image(dl),
                                            ],
                                            quote=False,
                                        )
                                        img_send = True
                                elif guess_type.extension in [
                                    "oga",
                                    "ogg",
                                    "flac",
                                    "mp3",
                                    "wav",
                                ]:
                                    if msg.Feature.voice:
                                        await msg.send_message(
                                            [
                                                I18NContext(
                                                    "wiki.message.wiki_inline.flies",
                                                    file=get_page.file,
                                                ),
                                                Voice(dl),
                                            ],
                                            quote=False,
                                        )
                            elif check_svg(dl):
                                rd = await svg_render(dl)
                                if msg.Feature.image and rd:
                                    chain = [
                                        I18NContext(
                                            "wiki.message.wiki_inline.flies",
                                            file=get_page.file,
                                        ),
                                    ]
                                    for r in rd:
                                        chain.append(Image(r))
                                    await msg.send_message(chain, quote=False)

                        if msg.Feature.image:
                            if (
                                get_page.status
                                and get_page.title
                                and (wiki_.wiki_info.in_allowlist or not Info.use_url_manager)
                            ):
                                if (
                                    wiki_.wiki_info.realurl
                                    not in generate_screenshot_v2_blocklist
                                ):
                                    is_disambiguation = False
                                    if get_page.templates:
                                        is_disambiguation = (
                                            "Template:Disambiguation"
                                            in get_page.templates
                                            or "Template:Version disambiguation"
                                            in get_page.templates
                                        )
                                    content_mode = (
                                        get_page.has_template_doc
                                        or get_page.title.split(":")[0] in ["User"]
                                        or is_disambiguation
                                        or get_page.is_forum_topic
                                    )
                                    get_infobox = await generate_screenshot_v2(
                                        qq,
                                        allow_special_page=(q[qq].in_allowlist or not Info.use_url_manager),
                                        content_mode=content_mode,
                                    )
                                    if get_infobox:
                                        imgs = []
                                        for img in get_infobox:
                                            imgs.append(Image(img))
                                        await msg.send_message(imgs, quote=False)
                                else:
                                    get_infobox = await generate_screenshot_v1(
                                        q[qq].realurl, qq, headers
                                    )
                                    if get_infobox:
                                        imgs = []
                                        for img in get_infobox:
                                            imgs.append(Image(img))
                                        await msg.send_message(imgs, quote=False)
                            if (
                                (
                                    get_page.invalid_section
                                    and (wiki_.wiki_info.in_allowlist or not Info.use_url_manager)
                                )
                                or (
                                    get_page.is_talk_page
                                    and not get_page.selected_section
                                )
                                and Info.web_render_status
                            ):
                                i_msg_lst = []
                                if get_page.sections:
                                    session_data = [
                                        [str(i + 1), get_page.sections[i]]
                                        for i in range(len(get_page.sections))
                                    ]
                                    i_msg_lst.append(
                                        I18NContext(
                                            "wiki.message.invalid_section.prompt"
                                            if (
                                                get_page.invalid_section
                                                and (wiki_.wiki_info.in_allowlist or not Info.use_url_manager)
                                            )
                                            else "wiki.message.talk_page.prompt"
                                        )
                                    )
                                    i_msg_lst += [
                                        Image(ii)
                                        for ii in await image_table_render(
                                            ImageTable(
                                                session_data,
                                                [
                                                    msg.locale.t(
                                                        "wiki.message.table.header.id"
                                                    ),
                                                    msg.locale.t(
                                                        "wiki.message.table.header.section"
                                                    ),
                                                ],
                                            )
                                        )
                                    ]
                                    i_msg_lst.append(
                                        I18NContext(
                                            "wiki.message.invalid_section.select"
                                        )
                                    )
                                    i_msg_lst.append(
                                        I18NContext("message.reply.prompt")
                                    )

                                    async def _callback(msg: Bot.MessageSession):
                                        display = msg.as_display(text_only=True)
                                        if isint(display):
                                            display = int(display)
                                            if display <= len(get_page.sections):
                                                get_page.selected_section = display - 1
                                                await query_pages(
                                                    msg,
                                                    title=get_page.title
                                                    + "#"
                                                    + get_page.sections[display - 1],
                                                    start_wiki_api=get_page.info.api,
                                                )

                                    await msg.send_message(
                                        i_msg_lst, callback=_callback
                                    )
                                else:
                                    await msg.send_message(
                                        I18NContext("wiki.message.invalid_section")
                                    )
                            if get_page.is_forum:
                                forum_data = get_page.forum_data
                                img_table_data = []
                                img_table_headers = ["#"]
                                for x in forum_data:
                                    if x == "#":
                                        img_table_headers += forum_data[x]["data"]
                                    else:
                                        img_table_data.append(
                                            [x] + forum_data[x]["data"]
                                        )
                                img_table = ImageTable(
                                    img_table_data, img_table_headers
                                )
                                i_msg_lst = []
                                i_msg_lst.append(
                                    I18NContext("wiki.message.forum.prompt")
                                )
                                i_msg_lst += [
                                    Image(ii)
                                    for ii in await image_table_render(img_table)
                                ]
                                i_msg_lst.append(
                                    I18NContext("wiki.message.invalid_section.select")
                                )
                                i_msg_lst.append(I18NContext("message.reply.prompt"))

                                async def _callback(msg: Bot.MessageSession):
                                    display = msg.as_display(text_only=True)
                                    if (
                                        isint(display)
                                        and int(display) <= len(forum_data) - 1
                                    ):
                                        await query_pages(
                                            msg,
                                            title=forum_data[display]["text"],
                                            start_wiki_api=get_page.info.api,
                                        )

                                await msg.send_message(i_msg_lst, callback=_callback)
                if len(query_list) == 1 and img_send:
                    return
                if msg.Feature.image:
                    for qq in q:
                        section_ = []
                        quote_code = False
                        page_name = urllib.parse.unquote(qq)
                        for qs in page_name:
                            if qs == "#":
                                quote_code = True
                            if qs == "?":
                                quote_code = False
                            if quote_code:
                                section_.append(qs)
                        if section_:
                            s = urllib.parse.unquote("".join(section_)[1:])
                            if q[qq].realurl and (q[qq].in_allowlist or not Info.use_url_manager):
                                if q[qq].realurl in generate_screenshot_v2_blocklist:
                                    get_section = await generate_screenshot_v1(
                                        q[qq].realurl, qq, headers, section=s
                                    )
                                else:
                                    get_section = await generate_screenshot_v2(
                                        qq, section=s
                                    )
                                if get_section:
                                    imgs = []
                                    for img in get_section:
                                        imgs.append(Image(img))
                                    await msg.send_message(imgs, quote=False)

    asyncio.create_task(bgtask())
    # await bgtask()
