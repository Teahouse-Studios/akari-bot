import asyncio
import re
from typing import Optional, Union

import filetype

from core.builtins import Bot, Plain, Image, Voice, Url, confirm_command
from core.builtins import MessageSession
from core.component import module
from core.constants.exceptions import AbuseWarning
from core.constants.info import Info
from core.logger import Logger
from core.utils.http import download
from core.utils.image import svg_render
from core.utils.image_table import image_table_render, ImageTable
from core.utils.text import isint
from .utils.dbutils import WikiTargetInfo
from .utils.mapping import generate_screenshot_v2_blocklist
from .utils.screenshot_image import generate_screenshot_v1, generate_screenshot_v2
from .utils.wikilib import WikiLib, PageInfo, InvalidWikiError, QueryInfo

wiki = module(
    "wiki",
    alias={
        "wiki_start_site": "wiki set",
        "interwiki": "wiki iw",
        "wiki iw set": "wiki iw add",
        "wiki iw del": "wiki iw remove",
        "wiki iw delete": "wiki iw remove",
    },
    recommend_modules="wiki_inline",
    developers=["OasisAkari"],
    doc=True,
)


@wiki.command(
    "<pagename> [-l <lang>] {{wiki.help}}", options_desc={"-l": "{wiki.help.option.l}"}
)
async def _(msg: Bot.MessageSession, pagename: str):
    get_lang = msg.parsed_msg.get("-l", False)
    if get_lang:
        lang = get_lang["<lang>"]
    else:
        lang = None
    await query_pages(msg, pagename, lang=lang)


@wiki.command(
    "id <pageid> [-l <lang>] {{wiki.help.id}}",
    options_desc={"-l": "{wiki.help.option.l}"},
)
async def _(msg: Bot.MessageSession, pageid: str):
    iw = None
    if match_iw := re.match(r"(.*?):(.*)", pageid):
        iw = match_iw.group(1)
        pageid = match_iw.group(2)
    if not isint(pageid):
        await msg.finish(msg.locale.t("wiki.message.id.invalid"))
    get_lang = msg.parsed_msg.get("-l", False)
    if get_lang:
        lang = get_lang["<lang>"]
    else:
        lang = None
    await query_pages(msg, pageid=pageid, iw=iw, lang=lang)


async def query_pages(
    session: Union[Bot.MessageSession, QueryInfo],
    title: Optional[Union[str, list, tuple]] = None,
    pageid: Optional[str] = None,
    iw: Optional[str] = None,
    lang: Optional[str] = None,
    preset_message: Optional[str] = None,
    start_wiki_api: Optional[str] = None,
    template: bool = False,
    mediawiki: bool = False,
    use_prefix: bool = True,
    inline_mode: bool = False,
):
    if isinstance(session, MessageSession):
        target = WikiTargetInfo(session)
        start_wiki = target.get_start_wiki()
        if start_wiki_api:
            start_wiki = start_wiki_api
        interwiki_list = target.get_interwikis()
        headers = target.get_headers()
        prefix = target.get_prefix()
    elif isinstance(session, QueryInfo):
        start_wiki = session.api
        interwiki_list = {}
        headers = session.headers
        prefix = session.prefix
    else:
        raise TypeError("Session must be Bot.MessageSession or QueryInfo.")

    if not start_wiki:
        if isinstance(session, Bot.MessageSession):
            await session.finish(
                session.locale.t("wiki.message.set.not_set", prefix=session.prefixes[0])
            )
    # if lang in interwiki_list:
    #     start_wiki = interwiki_list[lang]
    #     lang = None
    if title:
        if isinstance(title, str):
            title = [title]
        if len(title) > 15:
            raise AbuseWarning("{tos.message.reason.wiki_abuse}")
        query_task = {start_wiki: {"query": [], "iw_prefix": ""}}
        for t in title:
            if prefix and use_prefix:
                t = prefix + t
            if not t:
                continue
            if t[0] == ":":
                if len(t) > 1:
                    query_task[start_wiki]["query"].append(t[1:])
            else:
                match_interwiki = re.match(r"^(.*?):(.*)", t)
                matched = False
                if match_interwiki:
                    g1 = match_interwiki.group(1)
                    g2 = match_interwiki.group(2)
                    if g1 in interwiki_list:
                        interwiki_url = interwiki_list[g1]
                        if interwiki_url not in query_task:
                            query_task[interwiki_url] = {"query": [], "iw_prefix": g1}
                        query_task[interwiki_url]["query"].append(g2)
                        matched = True
                if not matched:
                    query_task[start_wiki]["query"].append(t)
    elif pageid:
        if not iw:
            query_task = {start_wiki: {"queryid": [pageid], "iw_prefix": ""}}
        else:
            if iw in interwiki_list:
                query_task = {
                    interwiki_list[iw]: {"queryid": [pageid], "iw_prefix": iw}
                }
            else:
                get_wiki_info = WikiLib(start_wiki)
                await get_wiki_info.fixup_wiki_info()
                if iw in get_wiki_info.wiki_info.interwiki:
                    query_task = {
                        get_wiki_info.wiki_info.interwiki[iw]: {
                            "queryid": [pageid],
                            "iw_prefix": iw,
                        }
                    }
                else:
                    raise ValueError(f'iw_prefix "{iw}" not found.')
    else:
        raise ValueError("Title or pageid must be specified.")
    Logger.debug(query_task)
    msg_list = []
    wait_msg_list = []
    wait_list = []
    wait_possible_list = []
    render_infobox_list = []
    render_section_list = []
    dl_list = []
    if preset_message:
        msg_list.append(Plain(preset_message))
    for q in query_task:
        current_task = query_task[q]
        ready_for_query_pages = current_task["query"] if "query" in current_task else []
        ready_for_query_ids = (
            current_task["queryid"] if "queryid" in current_task else []
        )
        iw_prefix = (
            (current_task["iw_prefix"] + ":") if current_task["iw_prefix"] != "" else ""
        )
        try:
            tasks = []
            for rd in ready_for_query_pages:
                if template:
                    rd = f"Template:{rd}"
                if mediawiki:
                    rd = f"MediaWiki:{rd}"
                tasks.append(
                    asyncio.ensure_future(
                        WikiLib(
                            q, headers, locale=session.locale.locale
                        ).parse_page_info(title=rd, inline=inline_mode, lang=lang)
                    )
                )
            for rdp in ready_for_query_ids:
                tasks.append(
                    asyncio.ensure_future(
                        WikiLib(
                            q, headers, locale=session.locale.locale
                        ).parse_page_info(pageid=rdp, inline=inline_mode, lang=lang)
                    )
                )
            query = await asyncio.gather(*tasks)
            for result in query:
                Logger.debug(result)
                r: PageInfo = result
                display_title = None
                display_before_title = None
                if r.title:
                    display_title = iw_prefix + r.title
                if r.before_title:
                    display_before_title = iw_prefix + r.before_title
                new_possible_title_list = []
                if r.possible_research_title:
                    for possible in r.possible_research_title:
                        new_possible_title_list.append(iw_prefix + possible)
                r.possible_research_title = new_possible_title_list
                if r.status:
                    plain_slice = []
                    if display_before_title and display_before_title != display_title:
                        if (
                            r.before_page_property == "template"
                            and r.page_property == "page"
                        ):
                            plain_slice.append(
                                session.locale.t(
                                    "wiki.message.redirect.template_to_page",
                                    title=display_before_title,
                                    redirected_title=display_title,
                                )
                            )
                        else:
                            plain_slice.append(
                                session.locale.t(
                                    "wiki.message.redirect",
                                    title=display_before_title,
                                    redirected_title=display_title,
                                )
                            )
                    if (
                        r.link
                        and r.selected_section
                        and r.info.in_allowlist
                        and not r.invalid_section
                        and Info.web_render_status
                    ):
                        render_section_list.append(
                            {
                                r.link: {
                                    "url": r.info.realurl,
                                    "section": r.selected_section,
                                    "in_allowlist": r.info.in_allowlist,
                                }
                            }
                        )
                        plain_slice.append(
                            session.locale.t("wiki.message.section.rendering")
                        )
                    else:
                        if r.desc:
                            plain_slice.append(r.desc)

                    if r.link:
                        plain_slice.append(
                            str(Url(r.link, use_mm=not r.info.in_allowlist))
                        )

                    if r.file:
                        dl_list.append(r.file)
                        plain_slice.append(
                            session.locale.t("wiki.message.flies") + r.file
                        )
                    else:
                        if r.link and not r.selected_section:
                            render_infobox_list.append(
                                {
                                    r.link: {
                                        "url": r.info.realurl,
                                        "in_allowlist": r.info.in_allowlist,
                                        "content_mode": r.has_template_doc
                                        or r.title.split(":")[0] in ["User"]
                                        or (
                                            r.templates
                                            and (
                                                "Template:Disambiguation" in r.templates
                                                or "Template:Version disambiguation"
                                                in r.templates
                                            )
                                        )
                                        or r.is_forum_topic,
                                    }
                                }
                            )
                    if plain_slice:
                        msg_list.append(Plain("\n".join(plain_slice)))
                    if Info.web_render_status:
                        if (r.invalid_section and r.info.in_allowlist) or (
                            r.is_talk_page and not r.selected_section
                        ):
                            if (
                                isinstance(session, Bot.MessageSession)
                                and session.Feature.image
                                and r.sections
                            ):
                                i_msg_lst = []
                                session_data = [
                                    [str(i + 1), r.sections[i]]
                                    for i in range(len(r.sections))
                                ]
                                i_msg_lst.append(
                                    Plain(
                                        session.locale.t(
                                            "wiki.message.invalid_section.prompt"
                                            if r.invalid_section and r.info.in_allowlist
                                            else "wiki.message.talk_page.prompt"
                                        )
                                    )
                                )
                                i_msg_lst += [
                                    Image(ii)
                                    for ii in await image_table_render(
                                        ImageTable(
                                            session_data,
                                            [
                                                session.locale.t(
                                                    "wiki.message.table.header.id"
                                                ),
                                                session.locale.t(
                                                    "wiki.message.table.header.section"
                                                ),
                                            ],
                                        )
                                    )
                                ]
                                i_msg_lst.append(
                                    Plain(
                                        session.locale.t(
                                            "wiki.message.invalid_section.select"
                                        )
                                    )
                                )
                                i_msg_lst.append(
                                    Plain(session.locale.t("message.reply.prompt"))
                                )

                                async def _callback(msg: Bot.MessageSession):
                                    display = msg.as_display(text_only=True)
                                    if isint(display):
                                        display = int(display)
                                        if display <= len(r.sections):
                                            r.selected_section = display - 1
                                            await query_pages(
                                                session,
                                                title=r.title
                                                + "#"
                                                + r.sections[display - 1],
                                                start_wiki_api=r.info.api,
                                            )

                                await session.send_message(
                                    i_msg_lst, callback=_callback
                                )
                            else:
                                if r.invalid_section and r.info.in_allowlist:
                                    msg_list.append(
                                        Plain(
                                            session.locale.t(
                                                "wiki.message.invalid_section"
                                            )
                                        )
                                    )
                        if r.is_forum:
                            if (
                                isinstance(session, Bot.MessageSession)
                                and session.Feature.image
                            ):
                                forum_data = r.forum_data
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
                                    Plain(session.locale.t("wiki.message.forum.prompt"))
                                )
                                i_msg_lst += [
                                    Image(ii)
                                    for ii in await image_table_render(img_table)
                                ]
                                i_msg_lst.append(
                                    Plain(
                                        session.locale.t(
                                            "wiki.message.invalid_section.select"
                                        )
                                    )
                                )
                                i_msg_lst.append(
                                    Plain(session.locale.t("message.reply.prompt"))
                                )

                                async def _callback(msg: Bot.MessageSession):
                                    display = msg.as_display(text_only=True)
                                    if (
                                        isint(display)
                                        and int(display) <= len(forum_data) - 1
                                    ):
                                        await query_pages(
                                            session,
                                            title=forum_data[display]["text"],
                                            start_wiki_api=r.info.api,
                                        )

                                await session.send_message(
                                    i_msg_lst, callback=_callback
                                )

                else:
                    plain_slice = []
                    wait_plain_slice = []
                    if display_title and display_before_title:
                        if (
                            isinstance(session, Bot.MessageSession)
                            and session.Feature.wait
                        ):
                            if not session.options.get("wiki_redlink", False):
                                if len(r.possible_research_title) > 1:
                                    wait_plain_slice.append(
                                        session.locale.t(
                                            "wiki.message.not_found.autofix.choice",
                                            title=display_before_title,
                                        )
                                    )
                                    pi = 0
                                    for p in r.possible_research_title:
                                        pi += 1
                                        wait_plain_slice.append(f"{pi}. {p}")
                                    wait_plain_slice.append(
                                        session.locale.t(
                                            "wiki.message.not_found.autofix.choice.prompt",
                                            number=str(
                                                r.possible_research_title.index(
                                                    display_title
                                                )
                                                + 1
                                            ),
                                        )
                                    )
                                    wait_possible_list.append(
                                        {
                                            display_before_title: {
                                                display_title: r.possible_research_title
                                            }
                                        }
                                    )
                                    wait_plain_slice.append(
                                        session.locale.t(
                                            "message.wait.prompt.next_message"
                                        )
                                    )
                                else:
                                    wait_plain_slice.append(
                                        session.locale.t(
                                            "wiki.message.not_found.autofix.confirm",
                                            title=display_before_title,
                                            redirected_title=display_title,
                                        )
                                    )
                                    wait_plain_slice.append(
                                        session.locale.t("message.wait.prompt.confirm")
                                    )
                            else:
                                if r.edit_link:
                                    plain_slice.append(
                                        r.edit_link
                                        + session.locale.t(
                                            "wiki.message.redlink.not_found"
                                        )
                                    )
                                else:
                                    plain_slice.append(
                                        session.locale.t(
                                            "wiki.message.redlink.not_found.uneditable",
                                            title=display_before_title,
                                        )
                                    )
                        else:
                            wait_plain_slice.append(
                                session.locale.t(
                                    "wiki.message.not_found.autofix",
                                    title=display_before_title,
                                    redirected_title=display_title,
                                )
                            )
                        if len(r.possible_research_title) == 1:
                            wait_list.append({display_title: display_before_title})
                    elif r.before_title:
                        plain_slice.append(
                            session.locale.t(
                                "wiki.message.not_found", title=display_before_title
                            )
                        )
                    elif r.id != -1:
                        plain_slice.append(
                            session.locale.t("wiki.message.id.not_found", id=str(r.id))
                        )
                    if r.desc:
                        plain_slice.append(r.desc)
                    if r.invalid_namespace and r.before_title:
                        plain_slice.append(
                            session.locale.t(
                                "wiki.message.invalid_namespace",
                                namespace=r.invalid_namespace,
                            )
                        )
                    if r.before_page_property == "template":
                        if r.before_title.split(":")[1].isupper():
                            plain_slice.append(
                                session.locale.t("wiki.message.magic_word")
                            )
                    if plain_slice:
                        msg_list.append(Plain("\n".join(plain_slice)))
                    if wait_plain_slice:
                        wait_msg_list.append(Plain("\n".join(wait_plain_slice)))
        except InvalidWikiError as e:
            if isinstance(session, Bot.MessageSession):
                await session.send_message(session.locale.t("message.error") + str(e))
            else:
                msg_list.append(Plain(session.locale.t("message.error") + str(e)))
    if isinstance(session, Bot.MessageSession):
        if msg_list:
            if all(
                [
                    not render_infobox_list,
                    not render_section_list,
                    not dl_list,
                    not wait_list,
                    not wait_possible_list,
                ]
            ):
                await session.finish(msg_list)
            else:
                await session.send_message(msg_list)

        async def infobox():
            if render_infobox_list and session.Feature.image:
                infobox_msg_list = []
                for i in render_infobox_list:
                    for ii in i:
                        Logger.info(i[ii]["url"])
                        if i[ii]["url"] not in generate_screenshot_v2_blocklist:

                            get_infobox = await generate_screenshot_v2(
                                ii,
                                allow_special_page=i[ii]["in_allowlist"],
                                content_mode=i[ii]["content_mode"],
                            )
                            if get_infobox:
                                for img in get_infobox:
                                    infobox_msg_list.append(Image(img))
                        else:
                            get_infobox = await generate_screenshot_v1(
                                i[ii]["url"],
                                ii,
                                headers,
                                allow_special_page=i[ii]["in_allowlist"],
                            )
                            if get_infobox:
                                for img in get_infobox:
                                    infobox_msg_list.append(Image(img))
                if infobox_msg_list:
                    await session.send_message(infobox_msg_list, quote=False)

        async def section():
            if render_section_list and session.Feature.image:
                section_msg_list = []
                for i in render_section_list:
                    for ii in i:
                        if i[ii]["in_allowlist"]:
                            if i[ii]["url"] not in generate_screenshot_v2_blocklist:
                                get_section = await generate_screenshot_v2(
                                    ii, section=i[ii]["section"]
                                )
                                if get_section:
                                    for img in get_section:
                                        section_msg_list.append(Image(img))
                                else:
                                    section_msg_list.append(
                                        Plain(
                                            session.locale.t(
                                                "wiki.message.error.render_section"
                                            )
                                        )
                                    )
                            else:
                                get_section = await generate_screenshot_v1(
                                    i[ii]["url"], ii, headers, section=i[ii]["section"]
                                )
                                if get_section:
                                    for img in get_section:
                                        section_msg_list.append(Image(img))
                                else:
                                    section_msg_list.append(
                                        Plain(
                                            session.locale.t(
                                                "wiki.message.error.render_section"
                                            )
                                        )
                                    )
                if section_msg_list:
                    await session.send_message(section_msg_list, quote=False)

        async def image_and_voice():
            def check_svg(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as file:
                        check = file.read(1024)
                        return "<svg" in check
                except Exception:
                    return False

            if dl_list:
                for f in dl_list:
                    dl = await download(f)
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
                            if session.Feature.image:
                                await session.send_message(Image(dl), quote=False)
                        elif guess_type.extension in [
                            "oga",
                            "ogg",
                            "flac",
                            "mp3",
                            "wav",
                        ]:
                            if session.Feature.voice:
                                await session.send_message(Voice(dl), quote=False)
                    elif check_svg(dl):
                        rd = await svg_render(dl)
                        if session.Feature.image and rd:
                            img_chain = []
                            for rr in rd:
                                img_chain.append(Image(rr))
                            await session.send_message(img_chain, quote=False)

        async def wait_confirm():
            if wait_msg_list and session.Feature.wait:
                confirm = await session.wait_next_message(
                    wait_msg_list, delete=True, append_instruction=False
                )
                auto_index = False
                index = 0
                if confirm.as_display(text_only=True) in confirm_command:
                    auto_index = True
                elif isint(confirm.as_display(text_only=True)):
                    index = int(confirm.as_display(text_only=True)) - 1
                else:
                    return
                preset_message = []
                wait_list_ = []
                for w in wait_list:
                    for wd in w:
                        preset_message.append(
                            session.locale.t(
                                "wiki.message.redirect.autofix",
                                title=w[wd],
                                redirected_title=wd,
                            )
                        )
                        wait_list_.append(wd)
                if auto_index:
                    for wp in wait_possible_list:
                        for wpk in wp:
                            keys = list(wp[wpk].keys())
                            preset_message.append(
                                session.locale.t(
                                    "wiki.message.redirect.autofix",
                                    title=wpk,
                                    redirected_title=keys[0],
                                )
                            )
                            wait_list_.append(keys[0])
                else:
                    for wp in wait_possible_list:
                        for wpk in wp:
                            keys = list(wp[wpk].keys())
                            if len(wp[wpk][keys[0]]) > index:
                                preset_message.append(
                                    session.locale.t(
                                        "wiki.message.redirect.autofix",
                                        title=wpk,
                                        redirected_title=wp[wpk][keys[0]][index],
                                    )
                                )
                                wait_list_.append(wp[wpk][keys[0]][index])

                if wait_list_:
                    await query_pages(
                        session,
                        wait_list_,
                        use_prefix=False,
                        preset_message="\n".join(preset_message),
                        lang=lang,
                    )

        asyncio.create_task(infobox())
        asyncio.create_task(section())
        asyncio.create_task(image_and_voice())
        asyncio.create_task(wait_confirm())
    else:
        return {
            "msg_list": msg_list,
            "web_render_list": render_infobox_list,
            "dl_list": dl_list,
            "wait_list": wait_list,
            "wait_msg_list": wait_msg_list,
        }
