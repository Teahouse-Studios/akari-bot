from typing import TYPE_CHECKING, Union

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
    async def send_keepalive_signal_to_server(cls, client_name: str, target_prefix_list: list = None, sender_prefix_list: list = None):
        await cls.add_job("Server", "client_keepalive",
                          {"client_name": client_name,
                           "target_prefix_list": target_prefix_list or [],
                           "sender_prefix_list": sender_prefix_list or []}, wait=False)


def get_session(args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    bot: "Bot" = exports["Bot"]
    if not session_info.fetch:
        ctx_manager = bot.ContextSlots[session_info.ctx_slot]
    else:
        ctx_manager = bot.ContextSlots[bot.fetched_session_ctx_slot]
    return session_info, bot, ctx_manager


@JobQueueClient.action("check_session_native_permission")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = get_session(args)
    return {"value": await ctx_manager.check_native_permission(session_info)}


@JobQueueClient.action("send_message")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = get_session(args)
    send = await ctx_manager.send_message(session_info,
                                          converter.structure(args["message"], Union[MessageChain, MessageNodes]),
                                          quote=args["quote"],
                                          enable_parse_message=args['enable_parse_message'],
                                          enable_split_image=args['enable_split_image'])
    return {"message_id": send}


@JobQueueClient.action("delete_message")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = get_session(args)
    await ctx_manager.delete_message(session_info, message_id=args["message_id"])
    return {"success": True}


@JobQueueClient.action("start_typing")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = get_session(args)
    await ctx_manager.start_typing(session_info)
    return {"success": True}


@JobQueueClient.action("end_typing")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = get_session(args)
    await ctx_manager.end_typing(session_info)
    return {"success": True}


@JobQueueClient.action("error_signal")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = get_session(args)
    await ctx_manager.error_signal(session_info)
    return {"success": True}


@JobQueueClient.action("hold_context")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = get_session(args)
    ctx_manager.hold_context(session_info)
    return {"success": True}


@JobQueueClient.action("release_context")
async def _(tsk: JobQueuesTable, args: dict):
    session_info, bot, ctx_manager = get_session(args)
    ctx_manager.release_context(session_info)
    return {"success": True}


add_export(JobQueueClient)
