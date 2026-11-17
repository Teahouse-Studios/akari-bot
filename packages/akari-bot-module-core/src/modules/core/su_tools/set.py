import re

import orjson

from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.loader import ModulesManager
from core.logger import Logger

set_ = module("set", required_superuser=True, base=True, doc=True)


@set_.command(
    "target module enable <target> <modules> ... {{I18N:core.help.set.target.module.enable}}",
    "target module disable <target> <modules> ... {{I18N:core.help.set.target.module.disable}}",
    "target module list <target> {{I18N:core.help.set.target.module.list}}",
)
async def _(msg: Bot.MessageSession, target: str):
    if not Alive.determine_target_from(target):
        await msg.finish(I18NContext("message.id.invalid.target", target=msg.session_info.target_from))
    target_union_info = await TargetUnionInfo.get_by_target_id(target, create=False)

    if not target_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.target.confirm"), append_instruction=False):
            await msg.finish()
        target_union_info = await TargetUnionInfo.resolve_union(target)
    if "enable" in msg.parsed_msg:
        modules = [
            m
            for m in [msg.parsed_msg["<modules>"]] + msg.parsed_msg.get("...", [])
            if m
            in ModulesManager.return_modules_list(
                msg.session_info.target_from, client_name=msg.session_info.client_name
            )
        ]
        await target_union_info.config_module(modules, True)
        if modules:
            await msg.finish(I18NContext("core.message.set.module.enable.success", modules=", ".join(modules)))
        else:
            await msg.finish(I18NContext("core.message.set.module.enable.failed"))
    elif "disable" in msg.parsed_msg:
        modules = [
            m for m in [msg.parsed_msg["<modules>"]] + msg.parsed_msg.get("...", []) if m in target_union_info.modules
        ]
        await target_union_info.config_module(modules, False)
        if modules:
            await msg.finish(I18NContext("core.message.set.module.disable.success", modules=", ".join(modules)))
        else:
            await msg.finish(I18NContext("core.message.set.module.disable.failed"))
    elif "list" in msg.parsed_msg:
        modules = sorted((await target_union_info.get()).modules)
        if modules:
            await msg.finish([I18NContext("core.message.set.module.list"), Plain(" | ".join(modules))])
        else:
            await msg.finish(I18NContext("core.message.set.module.list.none"))


@set_.command(
    "target data get <target> [<k>] {{I18N:core.help.set.target.data.get}}",
    "target data edit <target> <k> <v> {{I18N:core.help.set.target.data.edit}}",
    "target data delete <target> <k> {{I18N:core.help.set.target.data.delete}}",
)
async def _(msg: Bot.MessageSession, target: str):
    if not Alive.determine_target_from(target):
        await msg.finish(I18NContext("message.id.invalid.target", target=msg.session_info.target_from))
    target_union_info = await TargetUnionInfo.get_by_target_id(target, create=False)
    if not target_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.target.confirm"), append_instruction=False):
            await msg.finish()
        target_union_info = await TargetUnionInfo.resolve_union(target)
    if "get" in msg.parsed_msg:
        k = msg.parsed_msg.get("<k>", None)
        if k:
            res = target_union_info.target_data.get(k)
        else:
            res = target_union_info.target_data
        await msg.finish(str(res))
    elif "edit" in msg.parsed_msg:
        k = msg.parsed_msg.get("<k>")
        v = msg.parsed_msg.get("<v>")
        if isinstance(v, str):
            if re.match(r"\[.*\]|\{.*\}", v):
                try:
                    v = v.replace("'", '"')
                    v = orjson.loads(v)
                except orjson.JSONDecodeError as e:
                    Logger.error(str(e))
                    await msg.finish(I18NContext("message.failed"))
            elif v.lower() == "true":
                v = True
            elif v.lower() == "false":
                v = False
        await target_union_info.edit_target_data(k, v)
        await msg.finish(I18NContext("core.message.set.option.edit.success", k=k, v=v))
    elif "delete" in msg.parsed_msg:
        k = msg.parsed_msg.get("<k>")
        await target_union_info.edit_target_data(k, None)
        await msg.finish(I18NContext("message.success"))


@set_.command(
    "sender data get <user> [<k>] {{I18N:core.help.set.sender.data.get}}",
    "sender data edit <user> <k> <v> {{I18N:core.help.set.sender.data.edit}}",
    "sender data delete <user> <k> {{I18N:core.help.set.sender.data.delete}}",
)
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    if "get" in msg.parsed_msg:
        k = msg.parsed_msg.get("<k>", None)
        if k:
            res = sender_union_info.sender_data.get(k)
        else:
            res = sender_union_info.sender_data
        await msg.finish(str(res))
    elif "edit" in msg.parsed_msg:
        k = msg.parsed_msg.get("<k>")
        v = msg.parsed_msg.get("<v>")
        if isinstance(v, str):
            if re.match(r"\[.*\]|\{.*\}", v):
                try:
                    v = v.replace("'", '"')
                    v = orjson.loads(v)
                except orjson.JSONDecodeError as e:
                    Logger.error(str(e))
                    await msg.finish(I18NContext("message.failed"))
            elif v.lower() == "true":
                v = True
            elif v.lower() == "false":
                v = False
        await sender_union_info.edit_sender_data(k, v)
        await msg.finish(I18NContext("core.message.set.option.edit.success", k=k, v=v))
    elif "delete" in msg.parsed_msg:
        k = msg.parsed_msg.get("<k>")
        await sender_union_info.edit_sender_data(k, None)
        await msg.finish(I18NContext("message.success"))
