import orjson as json

from core.builtins import Bot, Plain, Image, Url
from core.config import Config
from core.constants import Info
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.utils.dbutils import WikiTargetInfo
from modules.wiki.utils.wikilib import WikiLib
from .wiki import wiki

enable_urlmanager = Config("enable_urlmanager", False)


@wiki.command("set <wikiurl> {{wiki.help.set}}", required_admin=True)
async def set_start_wiki(msg: Bot.MessageSession, wikiurl: str):
    target = WikiTargetInfo(msg)
    check = await WikiLib(wikiurl, headers=target.get_headers()).check_wiki_available()
    if check.available:
        in_allowlist = True
        if Info.use_url_manager:
            in_allowlist = check.value.in_allowlist
            if check.value.in_blocklist and not in_allowlist:
                await msg.finish(
                    msg.locale.t("wiki.message.invalid.blocked", name=check.value.name)
                )
        result = WikiTargetInfo(msg).add_start_wiki(check.value.api)
        if result and enable_urlmanager and not in_allowlist:
            prompt = "\n" + msg.locale.t("wiki.message.wiki_audit.untrust")
            if Config("wiki_whitelist_url", cfg_type=str):
                prompt += "\n" + msg.locale.t(
                    "wiki.message.wiki_audit.untrust.address",
                    url=Config("wiki_whitelist_url", cfg_type=str),
                )
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
    target = WikiTargetInfo(msg)
    check = await WikiLib(wikiurl, headers=target.get_headers()).check_wiki_available()
    if check.available:
        if (
            Info.use_url_manager
            and check.value.in_blocklist
            and not check.value.in_allowlist
        ):
            await msg.finish(
                msg.locale.t("wiki.message.invalid.blocked", name=check.value.name)
            )
        result = target.config_interwikis(interwiki, check.value.api, let_it=True)
        if result and enable_urlmanager and not check.value.in_allowlist:
            prompt = "\n" + msg.locale.t("wiki.message.wiki_audit.untrust")
            if Config("wiki_whitelist_url", cfg_type=str):
                prompt += "\n" + msg.locale.t(
                    "wiki.message.wiki_audit.untrust.address",
                    url=Config("wiki_whitelist_url", cfg_type=str),
                )

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
    target = WikiTargetInfo(msg)
    result = target.config_interwikis(interwiki, let_it=False)
    if result:
        await msg.finish(msg.locale.t("wiki.message.iw.remove.success", iw=interwiki))


@wiki.command(
    "iw list [--legacy] {{wiki.help.iw.list}}",
    options_desc={"--legacy": "{help.option.legacy}"},
)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    start_wiki = target.get_start_wiki()
    base_interwiki_link = None
    if start_wiki:
        base_interwiki_link_ = await WikiLib(
            start_wiki, target.get_headers()
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
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
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
    target = WikiTargetInfo(msg)
    headers = target.get_headers()
    prompt = msg.locale.t(
        "wiki.message.headers.show",
        headers=json.dumps(headers).decode(),
        prefix=msg.prefixes[0],
    )
    await msg.finish(prompt)


@wiki.command("headers add <headers> {{wiki.help.headers.add}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    add = target.config_headers(" ".join(msg.trigger_msg.split(" ")[3:]), let_it=True)
    if add:
        await msg.finish(
            msg.locale.t(
                "wiki.message.headers.add.success",
                headers=json.dumps(target.get_headers()).decode(),
            )
        )
    else:
        await msg.finish(msg.locale.t("wiki.message.headers.add.failed"))


@wiki.command(
    "headers remove <headerkey> {{wiki.help.headers.remove}}", required_admin=True
)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    delete = target.config_headers(
        " ".join(msg.trigger_msg.split(" ")[3:]), let_it=False
    )
    if delete:
        await msg.finish(
            msg.locale.t(
                "wiki.message.headers.add.success",
                headers=json.dumps(target.get_headers()).decode(),
            )
        )


@wiki.command("headers reset {{wiki.help.headers.reset}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    reset = target.config_headers("{}", let_it=None)
    if reset:
        await msg.finish(msg.locale.t("wiki.message.headers.reset.success"))


@wiki.command("prefix set <prefix> {{wiki.help.prefix.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, prefix: str):
    target = WikiTargetInfo(msg)
    set_prefix = target.set_prefix(prefix)
    if set_prefix:
        await msg.finish(
            msg.locale.t("wiki.message.prefix.set.success", wiki_prefix=prefix)
        )


@wiki.command("prefix reset {{wiki.help.prefix.reset}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    set_prefix = target.del_prefix()
    if set_prefix:
        await msg.finish(msg.locale.t("wiki.message.prefix.reset.success"))


@wiki.command("redlink {{wiki.help.redlink}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    redlink_state = msg.data.options.get("wiki_redlink")

    if redlink_state:
        msg.data.edit_option("wiki_redlink", False)
        await msg.finish(msg.locale.t("wiki.message.redlink.disable"))
    else:
        msg.data.edit_option("wiki_redlink", True)
        await msg.finish(msg.locale.t("wiki.message.redlink.enable"))
