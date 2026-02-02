from typing import TYPE_CHECKING

from core.builtins.session.info import SessionInfo
from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.message.chain import MessageChain, MessageNodes
from ..database.models import JobQueuesTable
from ..exports import exports, add_export

if TYPE_CHECKING:
    from core.builtins.bot import Bot


class JobQueueClient(JobQueueBase):

    @classmethod
    async def send_message_to_server(cls, session_info: SessionInfo):
        await cls.add_job("Server", "receive_message_from_client",
                          {"session_info": converter.unstructure(session_info)})

    @classmethod
    async def send_keepalive_signal_to_server(cls, client_name: str, target_prefix_list: list = None,
                                              sender_prefix_list: list = None):
        await cls.add_job("Server", "client_keepalive",
                          {"client_name": client_name,
                           "target_prefix_list": target_prefix_list or [],
                           "sender_prefix_list": sender_prefix_list or []}, wait=False)

    @classmethod
    async def trigger_hook(cls, module_or_hook_name: str, session_info: SessionInfo | None = "", wait=False,
                           **kwargs):
        for k in kwargs:
            if isinstance(kwargs[k], exports["MessageChain"]):
                kwargs[k] = kwargs[k].to_list()
        ret = await cls.add_job("Server", "trigger_hook",
                                {"module_or_hook_name": module_or_hook_name,
                                 "session_info": converter.unstructure(session_info) if session_info else "",
                                 "args": kwargs}, wait=wait)
        if wait:
            return ret["result"]
        return None

    @classmethod
    async def get_bot_version(cls):
        ret = await cls.add_job("Server", "get_bot_version", {})
        return ret["version"]

    @classmethod
    async def get_web_render_status(cls):
        ret = await cls.add_job("Server", "get_web_render_status", {})
        return ret["web_render_status"]

    @classmethod
    async def get_modules_list(cls):
        ret = await cls.add_job("Server", "get_modules_list", {})
        return ret["modules_list"]

    @classmethod
    async def get_modules_info(cls, locale: str = "zh_cn"):
        ret = await cls.add_job("Server", "get_modules_info", {"locale": locale})
        return ret["modules"]

    @classmethod
    async def get_module_helpdoc(cls, module: str, locale: str = "zh_cn"):
        ret = await cls.add_job("Server", "get_module_helpdoc", {"module": module, "locale": locale})
        return ret["help_doc"]

    @classmethod
    async def get_module_related(cls, module: str):
        ret = await cls.add_job("Server", "get_module_related", {"module": module})
        return ret["modules_list"]

    @classmethod
    async def post_module_action(cls, module: str, action: str):
        ret = await cls.add_job("Server", "post_module_action", {"module": module, "action": action})
        return ret["success"]


async def get_session(args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    await session_info.refresh_info()
    bot: "Bot" = exports["Bot"]
    if not session_info.fetch:
        ctx_manager = bot.ContextSlots[session_info.ctx_slot]
    else:
        ctx_manager = bot.ContextSlots[bot.fetched_session_ctx_slot]
    return session_info, bot, ctx_manager


@JobQueueClient.action("check_session_native_permission")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    return {"value": await ctx_manager.check_native_permission(session_info)}


@JobQueueClient.action("send_message")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    send = await ctx_manager.send_message(session_info,
                                          converter.structure(args["message"], MessageChain | MessageNodes),
                                          quote=args["quote"],
                                          enable_parse_message=args["enable_parse_message"],
                                          enable_split_image=args["enable_split_image"])
    return {"message_id": send}


@JobQueueClient.action("delete_message")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    await ctx_manager.delete_message(session_info, message_id=args["message_id"])
    return {"success": True}


@JobQueueClient.action("add_reaction")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    await ctx_manager.add_reaction(session_info, args["message_id"], args["emoji"])


@JobQueueClient.action("remove_reaction")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    await ctx_manager.add_reaction(session_info, args["message_id"], args["emoji"])


@JobQueueClient.action("start_typing")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    await ctx_manager.start_typing(session_info)
    return {"success": True}


@JobQueueClient.action("end_typing")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    await ctx_manager.end_typing(session_info)
    return {"success": True}


@JobQueueClient.action("error_signal")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    await ctx_manager.error_signal(session_info)
    return {"success": True}


@JobQueueClient.action("hold_context")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    ctx_manager.hold_context(session_info)
    return {"success": True}


@JobQueueClient.action("release_context")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    ctx_manager.release_context(session_info)
    return {"success": True}


@JobQueueClient.action("call_onebot_api")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = await get_session(args)
    get_ = getattr(ctx_manager, "call_onebot_api", None)
    if get_:
        g = await get_(args["api_name"], **args["args"])
        return g
    return {"success": False, "error": "API not supported in this context"}


add_export(JobQueueClient)
