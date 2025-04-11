import orjson as json

from core.builtins import Bot, Plain, Image, Url
from core.config import Config
from core.constants import Info, wiki_whitelist_url_default
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.database.models import WikiTargetInfo
from modules.wiki.utils.wikilib import WikiLib
from .wiki import wiki

enable_urlmanager = Config("enable_urlmanager", False)
wiki_whitelist_url = Config("wiki_whitelist_url", wiki_whitelist_url_default, table_name="module_wiki")


@wiki.command("set <wikiurl> {{wiki.help.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, wikiurl: str):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    check = await WikiLib(wikiurl, headers=target.headers).check_wiki_available()
    if check.available:
        in_allowlist = True
        if Info.use_url_manager:
            in_allowlist = check.value.in_allowlist
            if check.value.in_blocklist and not in_allowlist:
                await msg.finish(
                    msg.locale.t("wiki.message.invalid.blocked", name=check.value.name)
                )
        result = await target.add_start_wiki(check.value.api)
        if result and enable_urlmanager and not in_allowlist:
            prompt = "\n" + msg.locale.t("wiki.message.wiki_audit.untrust")
            if wiki_whitelist_url:
                prompt += "\n" + msg.locale.t("wiki.message.wiki_audit.untrust.address", url=wiki_whitelist_url)
        else:
            prompt = ""
        await msg.finish(
            msg.locale.t("wiki.message.set.success", name=check.value.name) + prompt
        )
    else:
        result = msg.locale.t("wiki.message.error.add") + (
            "\n" + msg.locale.t("wiki.message.error.info") + check.message
            if check.message != ""
            else ""
        )
        await msg.finish(result)


@wiki.command("iw add <interwiki> <wikiurl> {{wiki.help.iw.add}}", required_admin=True)
async def _(msg: Bot.MessageSession, interwiki: str, wikiurl: str):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    check = await WikiLib(wikiurl, headers=target.headers).check_wiki_available()
    if check.available:
        if (
            Info.use_url_manager
            and check.value.in_blocklist
            and not check.value.in_allowlist
        ):
            await msg.finish(
                msg.locale.t("wiki.message.invalid.blocked", name=check.value.name)
            )
        result = await target.config_interwikis(interwiki, check.value.api)
        if result and enable_urlmanager and not check.value.in_allowlist:
            prompt = "\n" + msg.locale.t("wiki.message.wiki_audit.untrust")
            if wiki_whitelist_url:
                prompt += "\n" + msg.locale.t("wiki.message.wiki_audit.untrust.address", url=wiki_whitelist_url)

        else:
            prompt = ""
        await msg.finish(
            msg.locale.t(
                "wiki.message.iw.add.success", iw=interwiki, name=check.value.name
            )
            + prompt
        )
    else:
        result = msg.locale.t("wiki.message.error.add") + (
            "\n" + msg.locale.t("wiki.message.error.info") + check.message
            if check.message != ""
            else ""
        )
        await msg.finish(result)


@wiki.command("iw remove <interwiki> {{wiki.help.iw.remove}}", required_admin=True)
async def _(msg: Bot.MessageSession, interwiki: str):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    result = await target.config_interwikis(interwiki)
    if result:
        await msg.finish(msg.locale.t("wiki.message.iw.remove.success", iw=interwiki))


@wiki.command(
    "iw list [--legacy] {{wiki.help.iw.list}}",
    options_desc={"--legacy": "{help.option.legacy}"},
)
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    query = target.interwikis
    start_wiki = target.api_link
    base_interwiki_link = None
    if start_wiki:
        base_interwiki_link_ = await WikiLib(
            start_wiki, target.headers
        ).parse_page_info("Special:Interwiki")
        if base_interwiki_link_.status:
            base_interwiki_link = base_interwiki_link_.link
    result = ""
    if query != {}:
        if not msg.parsed_msg.get("--legacy", False) and msg.Feature.image:
            columns = [[x, query[x]] for x in query]
            imgs = await image_table_render(ImageTable(columns, ["Interwiki", "Url"]))
        else:
            imgs = None
        if imgs:
            img_list = [Image(ii) for ii in imgs]
            mt = msg.locale.t("wiki.message.iw.list", prefix=msg.prefixes[0])
            if base_interwiki_link:
                mt += "\n" + msg.locale.t(
                    "wiki.message.iw.list.prompt", url=str(Url(base_interwiki_link))
                )
            await msg.finish(img_list + [Plain(mt)])
        else:
            result = (
                msg.locale.t("wiki.message.iw.list.legacy")
                + "\n"
                + "\n".join([f"{x}: {query[x]}" for x in query])
            )
    else:
        result = msg.locale.t("wiki.message.iw.list.none", prefix=msg.prefixes[0])
    if base_interwiki_link:
        result += "\n" + msg.locale.t(
            "wiki.message.iw.list.prompt", url=str(Url(base_interwiki_link))
        )
    await msg.finish(result)


@wiki.command("iw get <interwiki> {{wiki.help.iw.get}}")
async def _(msg: Bot.MessageSession, interwiki: str):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    query = target.interwikis
    if query != {}:
        if interwiki in query:
            await msg.finish(Url(query[interwiki]))
        else:
            await msg.finish(
                msg.locale.t("wiki.message.iw.get.not_found", iw=interwiki)
            )
    else:
        await msg.finish(
            msg.locale.t("wiki.message.iw.list.none", prefix=msg.prefixes[0])
        )


@wiki.command("headers show {{wiki.help.headers.show}}")
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    headers = target.headers
    prompt = msg.locale.t(
        "wiki.message.headers.show",
        headers=json.dumps(headers).decode(),
        prefix=msg.prefixes[0],
    )
    await msg.finish(prompt)


@wiki.command("headers add <headers> {{wiki.help.headers.add}}", required_admin=True)
async def _(msg: Bot.MessageSession, headers: str):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    add = await target.config_headers(headers)
    if add:
        await msg.finish(
            msg.locale.t(
                "wiki.message.headers.add.success",
                headers=json.dumps(target.headers).decode(),
            )
        )
    else:
        await msg.finish(msg.locale.t("wiki.message.headers.add.failed"))


@wiki.command(
    "headers remove <headerkey> {{wiki.help.headers.remove}}", required_admin=True
)
async def _(msg: Bot.MessageSession, headerkey: str):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    delete = await target.config_headers(headerkey, add=False)
    if delete:
        await msg.finish(
            msg.locale.t(
                "wiki.message.headers.add.success",
                headers=json.dumps(target.headers).decode(),
            )
        )


@wiki.command("headers reset {{wiki.help.headers.reset}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    reset = await target.config_headers()
    if reset:
        await msg.finish(msg.locale.t("wiki.message.headers.reset.success"))


@wiki.command("prefix set <prefix> {{wiki.help.prefix.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, prefix: str):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    set_prefix = await target.config_prefix(prefix)
    if set_prefix:
        await msg.finish(
            msg.locale.t("wiki.message.prefix.set.success", wiki_prefix=prefix)
        )


@wiki.command("prefix reset {{wiki.help.prefix.reset}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target = (await WikiTargetInfo.get_or_create(target_id=msg.target.target_id))[0]
    set_prefix = await target.config_prefix()
    if set_prefix:
        await msg.finish(msg.locale.t("wiki.message.prefix.reset.success"))


@wiki.command("redlink {{wiki.help.redlink}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    redlink_state = msg.target_data.get("wiki_redlink")

    if redlink_state:
        await msg.target_info.edit_target_data("wiki_redlink", False)
        await msg.finish(msg.locale.t("wiki.message.redlink.disable"))
    else:
        await msg.target_info.edit_target_data("wiki_redlink", True)
        await msg.finish(msg.locale.t("wiki.message.redlink.enable"))
