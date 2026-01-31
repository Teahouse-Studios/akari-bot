import os
from tabulate import tabulate
from tortoise import Tortoise
from tortoise.exceptions import OperationalError

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain, Image
from core.component import module
from core.constants import dev_mode, NoReportException
from core.database import fetch_module_db, get_model_fields, get_model_names
from core.utils.image_table import image_table_render, ImageTable
from core.utils.func import is_int

DBDATA_PER_PAGE = 10

_eval = module("eval", required_superuser=True, base=True, doc=True, load=dev_mode)


@_eval.command("<expr>")
async def _(msg: Bot.MessageSession, expr: str):
    try:
        await msg.finish(str(eval(expr, {"msg": msg, "Bot": Bot})), disable_secret_check=True)  # skipcq
    except Exception as e:
        raise NoReportException(str(e))


db = module("database", alias="db", required_superuser=True, base=True, doc=True, load=dev_mode)


@db.command("model")
async def _(msg: Bot.MessageSession):
    models_path = ["core.database.models"] + fetch_module_db()
    table_lst = sorted(get_model_names(models_path))
    await msg.finish([I18NContext("core.message.database.list")] + table_lst)


@db.command("field <model> [--legacy]")
async def _(msg: Bot.MessageSession, model: str):
    models_path = ["core.database.models"] + fetch_module_db()
    result = get_model_fields(models_path, model)

    if not result:
        await msg.finish(I18NContext("core.message.database.no_result"))

    headers = list(result[0].keys())
    data = [[str(v) for v in r.values()] for r in result]

    if not msg.parsed_msg.get("--legacy", False) and msg.session_info.support_image:
        table = ImageTable(data=data, headers=headers, session_info=msg.session_info, disable_joke=True)
        imgs = await image_table_render(table)
    else:
        imgs = None

    if imgs:
        img_list = [Image(ii) for ii in imgs]
        await msg.finish(img_list)
    else:
        table_str = tabulate(data, headers=headers, tablefmt="grid")
        await msg.finish(Plain(table_str, disable_joke=True))


@db.command("exec <sql> [-p <page>] [--legacy]")
async def _(msg: Bot.MessageSession, sql: str):
    try:
        conn = Tortoise.get_connection("default")
        if sql.upper().startswith("SELECT"):
            result = await conn.execute_query_dict(sql)

            if not result:
                await msg.finish(I18NContext("core.message.database.no_result"))

            headers = list(result[0].keys())
            data = [[str(v) for v in r.values()] for r in result]

            total_pages = (len(data) + DBDATA_PER_PAGE - 1) // DBDATA_PER_PAGE
            get_page = msg.parsed_msg.get("-p", False)

            page = (
                max(min(int(get_page["<page>"]), total_pages), 1)
                if get_page and is_int(get_page["<page>"])
                else 1
            )
            start_index = (page - 1) * DBDATA_PER_PAGE
            end_index = page * DBDATA_PER_PAGE
            page_data = data[start_index:end_index]

            footer = I18NContext(
                "core.message.database.pages",
                page=page,
                total_pages=total_pages,
                data_count=len(data))

            if not msg.parsed_msg.get("--legacy", False) and msg.session_info.support_image:
                table = ImageTable(data=page_data, headers=headers, session_info=msg.session_info, disable_joke=True)
                imgs = await image_table_render(table)
            else:
                imgs = None

            if imgs:
                img_list = [Image(ii) for ii in imgs]
                await msg.finish(img_list + [footer])
            else:
                table_str = tabulate(page_data, headers=headers, tablefmt="grid")
                await msg.finish([Plain(table_str, disable_joke=True), footer])

        rows, _ = await conn.execute_query(sql)
        await msg.finish(I18NContext("core.message.database.success", rows=rows))
    except OperationalError as e:
        raise NoReportException(str(e))
