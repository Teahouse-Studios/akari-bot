import re
from typing import TYPE_CHECKING

from core.builtins.parser.command import CommandParser
from core.builtins.parser.message import parser
from core.builtins.utils import command_prefix
from core.constants.path import PrivateAssets
from core.utils.bash import run_sys_command
from core.web_render import web_render
from ..alive import Alive
from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.message.chain import MessageChain, MessageNodes
from ..builtins.session.info import SessionInfo
from ..database.models import JobQueuesTable
from ..exports import exports, add_export
from ..i18n import Locale
from ..loader import ModulesManager
from ..logger import Logger

if TYPE_CHECKING:
    from core.builtins.bot import Bot


class JobQueueServer(JobQueueBase):

    @classmethod
    async def client_send_message(cls, session_info: SessionInfo, message: MessageChain | MessageNodes,
                                  quote: bool = True, wait=True,
                                  enable_parse_message: bool = True,
                                  enable_split_image: bool = True):
        value = await cls.add_job(session_info.client_name, "send_message",
                                  {"session_info": converter.unstructure(session_info),
                                   "message": converter.unstructure(message, MessageChain | MessageNodes),
                                   "quote": quote,
                                   "enable_parse_message": enable_parse_message,
                                   "enable_split_image": enable_split_image
                                   }, wait=wait)
        return value

    @classmethod
    async def client_delete_message(cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None):
        if isinstance(message_id, str):
            message_id = [message_id]
        value = await cls.add_job(session_info.client_name, "delete_message",
                                  {"session_info": converter.unstructure(session_info),
                                   "message_id": message_id,
                                   "reason": reason}, wait=False)
        return value

    @classmethod
    async def client_restrict_member(cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None = None, reason: str | None = None):
        value = await cls.add_job(session_info.client_name, "restrict_member",
                                  {"session_info": converter.unstructure(session_info),
                                   "user_id": user_id,
                                   "duration": duration,
                                   "reason": reason}, wait=False)
        return value

    @classmethod
    async def client_unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]):
        value = await cls.add_job(session_info.client_name, "unrestrict_member",
                                  {"session_info": converter.unstructure(session_info),
                                   "user_id": user_id}, wait=False)
        return value

    @classmethod
    async def client_kick_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None):
        value = await cls.add_job(session_info.client_name, "kick_member",
                                  {"session_info": converter.unstructure(session_info),
                                   "user_id": user_id,
                                   "reason": reason}, wait=False)
        return value

    @classmethod
    async def client_ban_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None):
        value = await cls.add_job(session_info.client_name, "ban_member",
                                  {"session_info": converter.unstructure(session_info),
                                   "user_id": user_id,
                                   "reason": reason}, wait=False)
        return value

    @classmethod
    async def client_unban_member(cls, session_info: SessionInfo, user_id: str | list[str]):
        value = await cls.add_job(session_info.client_name, "unban_member",
                                  {"session_info": converter.unstructure(session_info),
                                   "user_id": user_id}, wait=False)
        return value

    @classmethod
    async def client_add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str):
        value = await cls.add_job(session_info.client_name, "add_reaction",
                                  {"session_info": converter.unstructure(session_info),
                                   "message_id": message_id,
                                   "emoji": emoji})
        return value

    @classmethod
    async def client_remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str):
        value = await cls.add_job(session_info.client_name, "remove_reaction",
                                  {"session_info": converter.unstructure(session_info),
                                   "message_id": message_id,
                                   "emoji": emoji})
        return value

    @classmethod
    async def client_start_typing_signal(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "start_typing",
                                  {"session_info": converter.unstructure(session_info)})
        return value

    @classmethod
    async def client_end_typing_signal(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "end_typing",
                                  {"session_info": converter.unstructure(session_info)})
        return value

    @classmethod
    async def client_error_signal(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "error_signal",
                                  {"session_info": converter.unstructure(session_info)}, wait=False)
        return value

    @classmethod
    async def client_check_native_permission(cls, session_info: SessionInfo):
        v = await cls.add_job(session_info.client_name, "check_session_native_permission",
                              {"session_info": converter.unstructure(session_info)})
        return v["value"]

    @classmethod
    async def client_hold_context(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "hold_context",
                                  {"session_info": converter.unstructure(session_info)})
        return value

    @classmethod
    async def client_release_context(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "release_context",
                                  {"session_info": converter.unstructure(session_info)})
        return value

    @classmethod
    async def call_onebot_api(cls, session_info: SessionInfo, api_name: str, **kwargs: dict):
        value = await cls.add_job(session_info.client_name, "call_onebot_api",
                                  {"session_info": converter.unstructure(session_info),
                                   "api_name": api_name,
                                   "args": kwargs})
        return value


@JobQueueServer.action("receive_message_from_client")
async def receive_message_from_client(tsk: JobQueuesTable, args: dict):
    await parser(await exports["Bot"].MessageSession.from_session_info(
        converter.structure(args["session_info"], SessionInfo)))
    return {"success": True}


@JobQueueServer.action("client_keepalive")
async def client_keepalive(tsk: JobQueuesTable, args: dict):
    Alive.refresh_alive(tsk.args["client_name"],
                        target_prefix_list=tsk.args.get("target_prefix_list"),
                        sender_prefix_list=tsk.args.get("sender_prefix_list"))
    return {"success": True}


@JobQueueServer.action("trigger_hook")
async def _(tsk: JobQueuesTable, args: dict):
    bot: "Bot" = exports["Bot"]
    session_info: SessionInfo | None = None
    if args["session_info"]:
        session_info = converter.structure(args["session_info"], SessionInfo)
        await session_info.refresh_info()
    _val = await bot.Hook.trigger(args["module_or_hook_name"], session_info=session_info, args=args["args"])
    Logger.trace(
        f"Trigger hook {
            args["module_or_hook_name"]} with args {
            args["args"]}, result: {_val}, type: {
            type(_val)}")
    await JobQueueServer.return_val(tsk, {"result": _val})


@JobQueueServer.action("client_direct_message")
async def client_direct_message(tsk: JobQueuesTable, args: dict):
    bot: "Bot" = exports["Bot"]
    session_info = converter.structure(args["session_info"], SessionInfo)
    await session_info.refresh_info()
    message = converter.structure(args["message"], MessageChain | MessageNodes)
    await bot.send_direct_message(session_info, message, disable_secret_check=args["disable_secret_check"],
                                  enable_parse_message=args["enable_parse_message"])
    return {"success": True}


@JobQueueServer.action("get_bot_version")
async def get_bot_version(tsk: JobQueuesTable, args: dict):
    version = None
    version_path = PrivateAssets.path / ".version"
    if version_path.exists():
        with open(version_path, "r") as f:
            version = f.read()
    else:
        returncode, commit_hash, _ = await run_sys_command(["git", "rev-parse", "HEAD"])
        if returncode == 0:
            version = f"git:{commit_hash}"

    return {"version": version}


@JobQueueServer.action("get_web_render_status")
async def get_web_render_status(tsk: JobQueuesTable, args: dict):
    return {"web_render_status": await web_render.browser.check_status()}


@JobQueueServer.action("get_modules_list")
async def get_module_list(tsk: JobQueuesTable, args: dict):
    modules = {k: v.to_dict() for k, v in ModulesManager.return_modules_list(use_cache=False).items()}
    modules = {k: v for k, v in modules.items() if v.get("load", True) and not v.get("base", False)}
    module_list = []
    for module in modules.values():
        module_list.append(module["module_name"])
    return {"modules_list": module_list}


@JobQueueServer.action("get_modules_info")
async def get_modules_info(tsk: JobQueuesTable, args: dict):
    modules = {k: v.to_dict() for k, v in ModulesManager.return_modules_list(use_cache=False).items()}
    modules = {k: v for k, v in modules.items() if v.get("load", True)}

    for module in modules.values():
        if "desc" in module and module.get("desc"):
            module["desc"] = Locale(args["locale"]).t_str(module["desc"])

    return {"modules": modules}


@JobQueueServer.action("get_module_helpdoc")
async def get_module_helpdoc(tsk: JobQueuesTable, args: dict):
    module = ModulesManager.modules.get(args["module"], None)
    help_doc = {}
    if module:
        help_doc["module_name"] = module.module_name
        module_ = module.to_dict()
        if "desc" in module_ and module_.get("desc"):
            help_doc["desc"] = Locale(args["locale"]).t_str(module_["desc"])

        help_ = CommandParser(module,
                              module_name=module.module_name,
                              command_prefixes=[command_prefix[0]],
                              is_superuser=True)
        help_doc["commands"] = help_.return_json_help_doc(args["locale"])

        regex_ = []
        regex_list = module.regex_list.get(show_required_superuser=True)
        if regex_list:
            for regex in regex_list:
                pattern = None
                if isinstance(regex.pattern, str):
                    pattern = regex.pattern
                elif isinstance(regex.pattern, re.Pattern):
                    pattern = regex.pattern.pattern

                if pattern:
                    rdesc = regex.desc
                    if rdesc:
                        rdesc = Locale(args["locale"]).t_str(rdesc)

                    regex_.append({"pattern": pattern,
                                   "desc": rdesc})
        help_doc["regexp"] = regex_

    return {"help_doc": help_doc}


@JobQueueServer.action("get_module_related")
async def get_module_related(tsk: JobQueuesTable, args: dict):
    return {"modules_list": ModulesManager.search_related_module(args["module"], include_self=False)}


@JobQueueServer.action("post_module_action")
async def post_module_action(tsk: JobQueuesTable, args: dict):
    match args["action"]:
        case "reload":
            status, _ = await ModulesManager.reload_module(args["module"])
        case "load":
            status = await ModulesManager.load_module(args["module"])
        case "unload":
            status = await ModulesManager.unload_module(args["module"])
        case _:
            status = False
    return {"success": status}

add_export(JobQueueServer)
