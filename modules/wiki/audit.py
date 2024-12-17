import re
from datetime import timezone

from core.builtins import Bot, I18NContext, Image
from core.component import module
from core.constants import Info
from core.database.tables import is_mysql
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.utils.dbutils import Audit
from modules.wiki.utils.wikilib import WikiLib

aud = module(
    "wiki_audit",
    required_superuser=True,
    alias="wau",
    doc=True,
    load=Info.use_url_manager,
)


@aud.command(["trust <apilink>", "block <apilink>"])
async def _(msg: Bot.MessageSession, apilink: str):
    check = await WikiLib(apilink).check_wiki_available()
    if check.available:
        apilink = check.value.api
        if msg.parsed_msg.get("trust", False):
            res = Audit(apilink).add_to_AllowList()
            list_name = msg.locale.t("wiki.message.wiki_audit.list_name.allowlist")
        else:
            res = Audit(apilink).add_to_BlockList()
            list_name = msg.locale.t("wiki.message.wiki_audit.list_name.blocklist")
        if not res:
            await msg.finish(
                msg.locale.t(
                    "wiki.message.wiki_audit.add.failed",
                    list_name=list_name,
                    api=apilink,
                )
            )
        else:
            await msg.finish(
                msg.locale.t(
                    "wiki.message.wiki_audit.add.success",
                    list_name=list_name,
                    api=apilink,
                )
            )
    else:
        result = msg.locale.t("wiki.message.error.add") + (
            "\n" + msg.locale.t("wiki.message.error.info") + check.message
            if check.message != ""
            else ""
        )
        await msg.finish(result)


@aud.command(["distrust <apilink>", "unblock <apilink>"])
async def _(msg: Bot.MessageSession, apilink: str):
    if not re.match(r"^.*(/api\.php)$", apilink):
        await msg.finish(msg.locale.t("wiki.message.wiki_audit.remove.failed.not_api"))
    if msg.parsed_msg.get("distrust", False):
        res = Audit(apilink).remove_from_AllowList()  # 已关闭的站点无法验证有效性
        if not res:
            await msg.finish(
                msg.locale.t(
                    "wiki.message.wiki_audit.remove.failed.other_wiki", api=apilink
                )
            )
        list_name = msg.locale.t("wiki.message.wiki_audit.list_name.allowlist")
    else:
        res = Audit(apilink).remove_from_BlockList()
        list_name = msg.locale.t("wiki.message.wiki_audit.list_name.blocklist")
    if not res:
        await msg.finish(
            msg.locale.t(
                "wiki.message.wiki_audit.remove.failed",
                list_name=list_name,
                api=apilink,
            )
        )
    else:
        await msg.finish(
            msg.locale.t(
                "wiki.message.wiki_audit.remove.success",
                list_name=list_name,
                api=apilink,
            )
        )


@aud.command("query <apilink>")
async def _(msg: Bot.MessageSession, apilink: str):
    check = await WikiLib(apilink).check_wiki_available()
    if check.available:
        apilink = check.value.api
        audit = Audit(apilink)
        msg_list = []
        if audit.inAllowList:
            msg_list.append(
                msg.locale.t("wiki.message.wiki_audit.query.allowlist", api=apilink)
            )
        if audit.inBlockList:
            msg_list.append(
                msg.locale.t("wiki.message.wiki_audit.query.blocklist", api=apilink)
            )
        if msg_list:
            msg_list.append(msg.locale.t("wiki.message.wiki_audit.query.conflict"))
            await msg.finish(msg_list)
        else:
            await msg.finish(
                msg.locale.t("wiki.message.wiki_audit.query.none", api=apilink)
            )
    else:
        result = msg.locale.t("wiki.message.error.query") + (
            "\n" + msg.locale.t("wiki.message.error.info") + check.message
            if check.message != ""
            else ""
        )
        await msg.finish(result)


@aud.command("list [--legacy]")
async def _(msg: Bot.MessageSession):
    allow_list = Audit.get_allow_list()
    block_list = Audit.get_block_list()
    legacy = True
    if not msg.parsed_msg.get("--legacy", False) and msg.Feature.image:
        send_msgs = []
        if is_mysql:
            allow_columns = [
                [x[0], msg.ts2strftime(x[1].timestamp(), iso=True, timezone=False)]
                for x in allow_list
            ]
        else:
            allow_columns = [
                [
                    x[0],
                    msg.ts2strftime(
                        x[1].replace(tzinfo=timezone.utc).timestamp(),
                        iso=True,
                        timezone=False,
                    ),
                ]
                for x in allow_list
            ]

        if allow_columns:
            allow_table = ImageTable(
                data=allow_columns,
                headers=[
                    msg.locale.t("wiki.message.wiki_audit.list.table.header.apilink"),
                    msg.locale.t("wiki.message.wiki_audit.list.table.header.date"),
                ],
            )
            if allow_table:
                allow_image = await image_table_render(allow_table)
                if allow_image:
                    send_msgs.append(
                        I18NContext("wiki.message.wiki_audit.list.allowlist")
                    )
                    for im in allow_image:
                        send_msgs.append(Image(im))
        if is_mysql:
            block_columns = [
                [x[0], msg.ts2strftime(x[1].timestamp(), iso=True, timezone=False)]
                for x in block_list
            ]
        else:
            block_columns = [
                [
                    x[0],
                    msg.ts2strftime(
                        x[1].replace(tzinfo=timezone.utc).timestamp(),
                        iso=True,
                        timezone=False,
                    ),
                ]
                for x in block_list
            ]
        if block_columns:
            block_table = ImageTable(
                data=block_columns,
                headers=[
                    msg.locale.t("wiki.message.wiki_audit.list.table.header.apilink"),
                    msg.locale.t("wiki.message.wiki_audit.list.table.header.date"),
                ],
            )
            if block_table:
                block_image = await image_table_render(block_table)
                if block_image:
                    send_msgs.append(
                        I18NContext("wiki.message.wiki_audit.list.blocklist")
                    )
                    for im in block_image:
                        send_msgs.append(Image(im))
        if send_msgs:
            legacy = False
            await msg.finish(send_msgs)
    if legacy:
        wikis = []
        if allow_list:
            wikis.append(msg.locale.t("wiki.message.wiki_audit.list.allowlist"))
            for al in allow_list:
                wikis.append(
                    f"{al[0]} ({msg.ts2strftime(al[1].timestamp(), iso=True, timezone=False)})"
                )
        if block_list:
            wikis.append(msg.locale.t("wiki.message.wiki_audit.list.blocklist"))
            for bl in block_list:
                wikis.append(f"{bl[0]} ({bl[1]})")
        if wikis:
            await msg.finish(wikis)
        else:
            await msg.finish(msg.locale.t("wiki.message.wiki_audit.list.none"))
