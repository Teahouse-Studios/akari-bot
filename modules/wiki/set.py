import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Image, Plain, Url
from core.config import Config
from core.constants.default import wiki_whitelist_url_default
from core.utils.image_table import image_table_render, ImageTable
from . import wiki
from .database.models import WikiTargetInfo
from .utils.wikilib import WikiLib

enable_urlmanager = Config("enable_urlmanager", False)
wiki_whitelist_url = Config("wiki_whitelist_url", wiki_whitelist_url_default, table_name="module_wiki")


@wiki.command("set <wikiurl> {{I18N:wiki.help.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, wikiurl: str):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    check = await WikiLib(wikiurl, headers=target.headers).check_wiki_available()
    if check.available:
        wiki_name = check.value.name
        if check.value.lang:
            wiki_name += f' ({check.value.lang})'
        in_allowlist = True
        if Bot.Info.use_url_manager:
            in_allowlist = check.value.in_allowlist
            if check.value.in_blocklist and not in_allowlist:
                await msg.finish(I18NContext("wiki.message.invalid.blocked", name=wiki_name))
        result = await target.add_start_wiki(check.value.api)
        if result and enable_urlmanager and not in_allowlist:
            prompt = "\n" + msg.session_info.locale.t("wiki.message.wiki_audit.untrust")
            if wiki_whitelist_url:
                prompt += "\n" + \
                          msg.session_info.locale.t("wiki.message.wiki_audit.untrust.address", url=wiki_whitelist_url)
        else:
            prompt = ""
        await msg.finish(
            msg.session_info.locale.t("wiki.message.set.success", name=wiki_name) + prompt
        )
    else:
        result = msg.session_info.locale.t("wiki.message.error.add") + (
            "\n" + msg.session_info.locale.t("wiki.message.error.info") + check.message
            if check.message != ""
            else ""
        )
        await msg.finish(result)


@wiki.command("iw add <interwiki> <wikiurl> {{I18N:wiki.help.iw.add}}", required_admin=True)
async def _(msg: Bot.MessageSession, interwiki: str, wikiurl: str):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    check = await WikiLib(wikiurl, headers=target.headers).check_wiki_available()
    if check.available:
        wiki_name = check.value.name
        if check.value.lang:
            wiki_name += f' ({check.value.lang})'
        if (
            Bot.Info.use_url_manager
            and check.value.in_blocklist
            and not check.value.in_allowlist
        ):
            await msg.finish(
                msg.session_info.locale.t("wiki.message.invalid.blocked", name=wiki_name)
            )
        result = await target.config_interwikis(interwiki, check.value.api)
        if result and enable_urlmanager and not check.value.in_allowlist:
            prompt = "\n" + msg.session_info.locale.t("wiki.message.wiki_audit.untrust")
            if wiki_whitelist_url:
                prompt += "\n" + \
                          msg.session_info.locale.t("wiki.message.wiki_audit.untrust.address", url=wiki_whitelist_url)

        else:
            prompt = ""
        await msg.finish(
            msg.session_info.locale.t(
                "wiki.message.iw.add.success", iw=interwiki, name=wiki_name
            )
            + prompt
        )
    else:
        result = msg.session_info.locale.t("wiki.message.error.add") + (
            "\n" + msg.session_info.locale.t("wiki.message.error.info") + check.message
            if check.message != ""
            else ""
        )
        await msg.finish(result)


@wiki.command("iw remove <interwiki> {{I18N:wiki.help.iw.remove}}", required_admin=True)
async def _(msg: Bot.MessageSession, interwiki: str):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    result = await target.config_interwikis(interwiki)
    if result:
        await msg.finish(I18NContext("wiki.message.iw.remove.success", iw=interwiki))


@wiki.command(
    "iw list [--legacy] {{I18N:wiki.help.iw.list}}",
    options_desc={"--legacy": "{I18N:help.option.legacy}"},
)
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    query = target.interwikis
    start_wiki = target.api_link
    base_interwiki_link = None
    if start_wiki:
        base_interwiki_link_ = await WikiLib(
            start_wiki, target.headers
        ).parse_page_info("Special:Interwiki", session=msg)
        if base_interwiki_link_.status:
            base_interwiki_link = base_interwiki_link_.link
    result = []
    if query != {}:
        if not msg.parsed_msg.get("--legacy", False) and msg.session_info.support_image:
            columns = [[x, query[x]] for x in query]
            imgs = await image_table_render(ImageTable(columns, ["Interwiki", "Url"]))
        else:
            imgs = None
        if imgs:
            img_list = [Image(ii) for ii in imgs]
            mt = [I18NContext("wiki.message.iw.list", prefix=msg.session_info.prefixes[0])]
            if base_interwiki_link:
                mt.append(I18NContext("wiki.message.iw.list.prompt", url=str(Url(base_interwiki_link))))
            await msg.finish(img_list + mt)
        else:
            result.append(I18NContext("wiki.message.iw.list.legacy"))
            for x in query:
                result.append(Plain(f"{x}: {query[x]}"))
    else:
        result.append(I18NContext("wiki.message.iw.list.none", prefix=msg.session_info.prefixes[0]))
    if base_interwiki_link:
        result.append(I18NContext("wiki.message.iw.list.prompt", url=str(Url(base_interwiki_link))))
    await msg.finish(result)


@wiki.command("iw get <interwiki> {{I18N:wiki.help.iw.get}}")
async def _(msg: Bot.MessageSession, interwiki: str):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    query = target.interwikis
    if query != {}:
        if interwiki in query:
            await msg.finish(Url(query[interwiki], use_mm=False))
        else:
            await msg.finish(I18NContext("wiki.message.iw.get.not_found", iw=interwiki))
    else:
        await msg.finish(I18NContext("wiki.message.iw.list.none", prefix=msg.session_info.prefixes[0]))


@wiki.command("headers show {{I18N:wiki.help.headers.show}}")
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    await msg.finish(I18NContext("wiki.message.headers.show",
                                 headers=orjson.dumps(target.headers).decode(),
                                 prefix=msg.session_info.prefixes[0]
                                 ))


@wiki.command("headers add <headers> {{I18N:wiki.help.headers.add}}", required_admin=True)
async def _(msg: Bot.MessageSession, headers: str):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    add = await target.config_headers(headers)
    if add:
        await msg.finish(I18NContext("wiki.message.headers.add.success", headers=orjson.dumps(target.headers).decode()))
    else:
        await msg.finish(I18NContext("wiki.message.headers.add.failed"))


@wiki.command(
    "headers remove <headerkey> {{I18N:wiki.help.headers.remove}}", required_admin=True
)
async def _(msg: Bot.MessageSession, headerkey: str):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    delete = await target.config_headers(headerkey, add=False)
    if delete:
        await msg.finish(I18NContext("wiki.message.headers.add.success", headers=orjson.dumps(target.headers).decode()))


@wiki.command("headers reset {{I18N:wiki.help.headers.reset}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    reset = await target.config_headers()
    if reset:
        await msg.finish(I18NContext("wiki.message.headers.reset.success"))


@wiki.command("prefix set <prefix> {{I18N:wiki.help.prefix.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, prefix: str):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    set_prefix = await target.config_prefix(prefix)
    if set_prefix:
        await msg.finish(I18NContext("wiki.message.prefix.set.success", wiki_prefix=prefix))


@wiki.command("prefix reset {{I18N:wiki.help.prefix.reset}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target = await WikiTargetInfo.get_by_target_id(msg.session_info.target_id)
    set_prefix = await target.config_prefix()
    if set_prefix:
        await msg.finish(I18NContext("wiki.message.prefix.reset.success"))


@wiki.command("redlink {{I18N:wiki.help.redlink}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    redlink_state = msg.session_info.target_info.target_data.get("wiki_redlink")

    if redlink_state:
        await msg.session_info.target_info.edit_target_data("wiki_redlink", False)
        await msg.finish(I18NContext("wiki.message.redlink.disable"))
    else:
        await msg.session_info.target_info.edit_target_data("wiki_redlink", True)
        await msg.finish(I18NContext("wiki.message.redlink.enable"))
