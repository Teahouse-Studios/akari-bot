import re
import urllib.parse

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Button, ButtonFrame, ButtonRows, I18NContext, Image, Url
from core.component import module
from core.utils.dirty_check import check
from core.logger import Logger
from core.utils.image_table import image_table_render, ImageTable
from core.utils.button import build_button_rows
from .database.models import WikiTargetInfo
from .utils.diff import DiffError, parse_diff_target
from .utils.forum import build_forum_markdown_table, build_section_markdown_table
from .utils.mapping import generate_screenshot_v2_blocklist
from .utils.screenshot_image import generate_screenshot
from .utils.media import file_preview
from .utils.wikilib import WikiLib, PageInfo
from .wiki import (
    WIKI_RENDER_MODE_AUTO,
    WIKI_RENDER_MODE_BUTTON,
    _WikiMessageTracker,
    _build_forum_callback,
    _build_render_preview_callback,
    _build_section_callback,
    _start_background_with_release,
    _wiki_render_mode,
    query_expressions,
    query_pages,
)

wiki_inline = module(
    "wiki-inline",
    desc="{I18N:wiki.help.wiki-inline.desc}",
    doc=True,
    recommend_modules=["wiki"],
    alias=["wiki_inline", "wiki_regex"],
    developers=["OasisAkari"],
    regex=True,
)


@wiki_inline.regex(r"\[\[(.*?)\]\]", flags=re.I, mode="A", desc="{I18N:wiki.help.wiki-inline.page}")
async def _(msg: Bot.MessageSession):
    query_list = []
    for x in msg.matched_msg:
        if x != "" and x not in query_list and x[0] != "#":
            query_list.append(x.split("|")[0])
    if query_list:
        await query_pages(msg, query_list[:5], inline_mode=True)


@wiki_inline.regex(
    r"\{\{",
    mode="A",
    desc="{I18N:wiki.help.wiki-inline.template}",
)
async def inline_templates(msg: Bot.MessageSession):
    await query_expressions(msg, msg.as_display(text_only=True), inline=True)


@wiki_inline.regex(
    r"≺(.*?)≻|⧼(.*?)⧽", flags=re.I, mode="A", show_typing=False, desc="{I18N:wiki.help.wiki-inline.mediawiki}"
)
async def _(msg: Bot.MessageSession):
    query_list = []
    for x in msg.matched_msg:
        for y in x:
            if y != "" and y not in query_list and y[0] != "#":
                query_list.append(y)
    if query_list:
        await query_pages(msg, query_list[:5], mediawiki=True, inline_mode=True)


async def _read_url_page(wiki: WikiLib, url: str, msg: Bot.MessageSession, *, check_render: bool) -> PageInfo | None:
    parts = urllib.parse.urlsplit(url)
    params = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    if "oldid" in params and params["oldid"] != ["0"]:
        return await wiki.parse_page_info(url, session=msg, check_render=check_render)
    if params.get("oldid") == ["0"]:
        del params["oldid"]
    title = WikiLib._title_from_article_url(url, wiki.wiki_info.articlepath) or params.get("title", [None])[0]
    if title:
        args = {key: values[0] for key, values in params.items() if key not in {"title", "curid"} and len(values) == 1}
        if args:
            title += "?" + urllib.parse.urlencode(args)
        if parts.fragment:
            title += "#" + urllib.parse.unquote(parts.fragment)
        return await wiki.parse_page_info(title, session=msg, check_render=check_render)
    pageid = params.get("curid", [""])[0]
    if pageid.isdecimal():
        page = await wiki.parse_page_info(pageid=int(pageid), session=msg, check_render=check_render)
        if page.status and parts.fragment:
            return await wiki.parse_page_info(
                page.title + "#" + urllib.parse.unquote(parts.fragment), session=msg, check_render=check_render
            )
        return page
    return None


async def _send_url_preview(msg: Bot.MessageSession, page: PageInfo, headers: dict) -> None:
    allowed = page.info.is_allowed or not msg.session_info.use_url_manager
    if not (page.status and page.link and page.renderable and allowed and msg.session_info.support_image):
        return
    item = {
        "link": page.link,
        "wiki_info": page.info,
        "title": page.title,
        "section": page.selected_section,
        "is_allowed": allowed and page.info.realurl not in generate_screenshot_v2_blocklist,
        "content_mode": page.has_template_doc
        or page.is_disambiguation
        or page.is_forum_topic
        or page.title.split(":")[0] == "User",
        "diff_data": page.diff_data,
    }
    tracker = _WikiMessageTracker(msg)
    buttons = ButtonFrame(
        [
            ButtonRows.assign(
                [
                    Button(
                        msg.t("wiki.message.render.action.button"),
                        "wiki_render_preview",
                        permission="all",
                        click_limit=1,
                    ),
                    Button(msg.t("wiki.message.render.action.delete"), "wiki_render_delete", click_limit=1),
                ]
            )
        ]
    )
    detection_key = (
        "wiki.message.wiki-inline.detected.section"
        if page.selected_section
        else "wiki.message.wiki-inline.detected.page"
    )
    detection_title = (
        urllib.parse.unquote(page.selected_section).replace("_", " ") if page.selected_section else page.title
    )
    await tracker.add(
        await msg.send_message(
            [I18NContext(detection_key, title=detection_title), buttons],
            callback=_build_render_preview_callback([item], headers, tracker),
            callback_once=False,
            quote=False,
        )
    )


@wiki_inline.regex(
    r"(https?://[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,4}\b[-a-zA-Z0-9@:%_+.~#?&/=]*)",
    flags=re.I,
    mode="A",
    show_typing=False,
    logging=False,
    skip_long_message_confirm=True,
    desc="{I18N:wiki.help.wiki-inline.url}",
)
async def _parse_wiki_urls(msg: Bot.MessageSession):
    match_msg = msg.matched_msg
    render_mode = _wiki_render_mode(msg)

    async def _run_bgtask(query_list):
        Logger.trace(query_list)
        for q in query_list:
            for qq in q:
                wiki_ = WikiLib(qq, headers=headers, locale=msg.session_info.locale.locale)
                wiki_.wiki_info = q[qq]
                try:
                    diff_target = parse_diff_target(qq, q[qq])
                except DiffError:
                    diff_target = {}
                if diff_target is not None:
                    await query_pages(msg, qq, start_wiki_api=q[qq].api, use_prefix=False, inline_mode=True)
                    continue
                try:
                    get_page = await _read_url_page(wiki_, qq, msg, check_render=render_mode == WIKI_RENDER_MODE_BUTTON)
                except Exception:
                    Logger.exception("Failed to query Wiki URL: ")
                    continue
                if get_page:
                    if not get_page.info.is_allowed and msg.session_info.use_url_manager:
                        checked = await check(get_page.title or "", session=msg)
                        if any(not result["status"] for result in checked):
                            continue
                    if get_page.status and get_page.file:
                        preview = await file_preview(get_page.file, msg.session_info)
                        if preview:
                            await msg.send_message(
                                [
                                    I18NContext(
                                        "wiki.message.wiki-inline.flies", file=MessageChain.assign(Url(get_page.file))
                                    )
                                ]
                                + list(preview),
                                quote=False,
                            )
                        continue
                    if render_mode != WIKI_RENDER_MODE_AUTO:
                        if render_mode == WIKI_RENDER_MODE_BUTTON and Bot.Info.web_render_status:
                            await _send_url_preview(msg, get_page, headers)
                        continue
                    if msg.session_info.support_image:
                        if (
                            Bot.Info.web_render_status
                            and get_page.status
                            and get_page.title
                            and not get_page.invalid_section
                            and (wiki_.wiki_info.is_allowed or not msg.session_info.use_url_manager)
                        ):
                            content_mode = (
                                get_page.has_template_doc
                                or get_page.title.split(":")[0] in ["User"]
                                or get_page.is_disambiguation
                                or get_page.is_forum_topic
                            )
                            get_infobox = await generate_screenshot(
                                get_page.link or qq,
                                wiki_info=get_page.info,
                                title=get_page.title,
                                section=get_page.selected_section,
                                headers=headers,
                                allow_special_page=(
                                    get_page.info.realurl not in generate_screenshot_v2_blocklist
                                    and (get_page.info.is_allowed or not msg.session_info.use_url_manager)
                                ),
                                content_mode=content_mode,
                                locale=msg.session_info.locale.locale,
                            )
                            if get_infobox:
                                imgs = []
                                for img in get_infobox:
                                    imgs.append(Image(img))
                                await msg.send_message(imgs, quote=False)
                        if (
                            (
                                get_page.invalid_section
                                and (wiki_.wiki_info.is_allowed or not msg.session_info.use_url_manager)
                            )
                            or (get_page.is_talk_page and not get_page.selected_section)
                            and Bot.Info.web_render_status
                        ):
                            i_msg_lst = []
                            if get_page.sections:
                                button_data_ = []
                                if msg.session_info.support_button:
                                    for i in range(len(get_page.sections)):
                                        button_data_.append({str(i + 1): str(i + 1)})
                                Logger.debug(button_data_)
                                button_data = []
                                rb = {}
                                for b in button_data_[0:50]:
                                    rb.update(b)
                                    if len(rb.keys()) >= 10:
                                        button_data.append(rb.copy())
                                        rb.clear()
                                if rb:
                                    button_data.append(rb)

                                Logger.debug(button_data)
                                i_msg_lst.append(
                                    I18NContext(
                                        "wiki.message.invalid_section.prompt"
                                        if get_page.invalid_section
                                        and (
                                            get_page.info.is_allowed
                                            or not (
                                                isinstance(msg, Bot.MessageSession) and msg.session_info.use_url_manager
                                            )
                                        )
                                        else "wiki.message.talk_page.prompt"
                                    )
                                )
                                use_markdown_section = (
                                    msg.session_info.client_name == "QQBot"
                                    and msg.session_info.support_markdown
                                    and msg.session_info.support_markdown_extension
                                    and msg.session_info.support_action_text
                                )
                                if use_markdown_section:
                                    i_msg_lst.extend(
                                        build_section_markdown_table(
                                            get_page.sections, get_page.title, msg.session_info.prefixes[0]
                                        )
                                    )
                                else:
                                    session_data = [
                                        [str(i + 1), get_page.sections[i]] for i in range(len(get_page.sections))
                                    ]
                                    i_msg_lst += [
                                        Image(ii)
                                        for ii in await image_table_render(
                                            ImageTable(
                                                session_data,
                                                [
                                                    msg.t("wiki.message.table.header.id"),
                                                    msg.t("wiki.message.table.header.section"),
                                                ],
                                            )
                                        )
                                    ]
                                    if not msg.session_info.support_button:
                                        i_msg_lst.append(I18NContext("wiki.message.invalid_section.select"))
                                        i_msg_lst.append(I18NContext("message.wait.reply.prompt"))
                                    elif len(button_data_) > 50:
                                        i_msg_lst.append(
                                            I18NContext("wiki.message.invalid_section.select.button.limit")
                                        )

                                if button_data and not use_markdown_section:
                                    i_msg_lst.append(ButtonFrame(build_button_rows(button_data)))
                                if use_markdown_section:
                                    await msg.send_message(i_msg_lst)
                                else:
                                    await msg.send_message(i_msg_lst, callback=_build_section_callback(get_page))
                            else:
                                await msg.send_message(I18NContext("wiki.message.invalid_section"))
                        if get_page.is_forum:
                            forum_data = get_page.forum_data
                            use_markdown_forum = (
                                msg.session_info.client_name == "QQBot"
                                and msg.session_info.support_markdown
                                and msg.session_info.support_markdown_extension
                                and msg.session_info.support_action_text
                            )
                            img_table_data = []
                            img_table_headers = ["#"]
                            button_data = []

                            for x in forum_data:
                                if x == "#":
                                    img_table_headers += forum_data[x]["data"]
                                else:
                                    img_table_data.append([x] + forum_data[x]["data"])
                            rb = {}
                            bi = 1
                            for b in forum_data:
                                if b != "#":
                                    rb.update({b: b})
                                    if len(rb.keys()) >= 5:
                                        button_data.append(rb.copy())
                                        rb.clear()
                                if bi == 25:
                                    break
                                bi += 1
                            if rb:
                                button_data.append(rb)
                            Logger.debug(f"Button data: {button_data}")
                            i_msg_lst = []
                            i_msg_lst.append(I18NContext("wiki.message.forum.prompt"))
                            if use_markdown_forum:
                                i_msg_lst.extend(build_forum_markdown_table(forum_data, msg.session_info.prefixes[0]))
                            else:
                                img_table = ImageTable(img_table_data, img_table_headers)
                                i_msg_lst += [Image(ii) for ii in await image_table_render(img_table)]
                                if not msg.session_info.support_button:
                                    i_msg_lst.append(I18NContext("wiki.message.invalid_section.select"))
                                    i_msg_lst.append(I18NContext("message.wait.reply.prompt"))
                                else:
                                    i_msg_lst.append(I18NContext("wiki.message.invalid_section.select.button"))
                                    if len(forum_data) > 25:
                                        i_msg_lst.append(
                                            I18NContext("wiki.message.invalid_section.select.button.limit")
                                        )

                            if button_data and not use_markdown_forum:
                                i_msg_lst.append(ButtonFrame(build_button_rows(button_data)))
                            if use_markdown_forum:
                                await msg.send_message(i_msg_lst)
                            else:
                                await msg.send_message(i_msg_lst, callback=_build_forum_callback(get_page))

    _query_list = []
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    headers = target.headers
    for x in match_msg:
        try:
            wiki_ = WikiLib(x)
            if check_from_database := await wiki_.check_wiki_info_from_database_cache():
                if check_from_database.available:
                    check_from_api = await wiki_.check_wiki_available()
                    if check_from_api.available:
                        _query_list.append({x: check_from_api.value})
        except Exception:
            Logger.exception("Error occurred while checking wiki info for query: ")

    if _query_list:
        await _start_background_with_release(
            msg,
            lambda: _run_bgtask(tuple(_query_list)),
            name="wiki-inline-background",
        )
