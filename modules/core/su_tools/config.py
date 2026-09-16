import re

import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.config import CFGManager
from core.logger import Logger
from core.types import Param
from core.utils.func import is_float, is_int

cfg_ = module("config", required_superuser=True, alias="cfg", base=True, doc=True)


@cfg_.command("get <k> [<table_name>] {{I18N:core.help.config.get}}")
async def _(msg: Bot.MessageSession, k: str, table_name: str | None = None):
    await msg.finish(str(CFGManager.get(k, table_name=table_name)))


@cfg_.command(
    "write <k> <v> [<table_name>] [-s] {{I18N:core.help.config.write}}",
    options_desc={"-s": "{I18N:core.help.config.write.option.s}"},
)
async def _(msg: Bot.MessageSession, k: str, v: str, table_name: str | None = None, secret: Param("-s", bool) = False):
    if v.lower() == "true":
        v_ = True
    elif v.lower() == "false":
        v_ = False
    elif is_int(v):
        v_ = int(v)
    elif is_float(v):
        v_ = float(v)
    elif re.match(r"\[.*\]", v):
        try:
            v = v.replace("'", '"')
            v_ = orjson.loads(v)
        except orjson.JSONDecodeError as e:
            Logger.error(str(e))
            await msg.finish(I18NContext("message.failed"))
    else:
        v_ = v

    if (not table_name and secret) or (table_name and table_name.lower() == "secret"):
        table_name = "config"
        secret = True

    if not CFGManager.has(k, secret=secret, table_name=table_name):
        # 新建配置项会改变配置文件结构，与改写已有值不同，需额外确认
        if not await msg.wait_confirm(
            I18NContext(
                "core.message.config.write.create.confirm",
                k=k,
                table=table_name,
            ),
            append_instruction=False,
        ):
            await msg.finish()

    CFGManager.edit_write(k, v_, secret=secret, table_name=table_name)
    await msg.finish(I18NContext("message.success"))


@cfg_.command("delete <k> [<table_name>] {{I18N:core.help.config.delete}}")
async def _(msg: Bot.MessageSession, k: str, table_name: str | None = None):
    if CFGManager.edit_delete(k, table_name):
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("message.failed"))
