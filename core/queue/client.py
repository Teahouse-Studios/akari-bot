import traceback
from typing import TYPE_CHECKING

from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.message.chain import MessageChain
from ..builtins.session import SessionInfo
from ..database.models import JobQueuesTable
from ..exports import exports, add_export
from ..logger import Logger

if TYPE_CHECKING:
    from core.builtins import Bot


class JobQueueClient(JobQueueBase):

    @classmethod
    async def send_message_signal_to_server(cls, session_info: SessionInfo):
        await cls.add_job("Server", "receive_message_from_client",
                          {"session_info": converter.unstructure(session_info)})

    @classmethod
    async def send_keepalive_signal_to_server(cls, client_name: str, target_prefix_list: list = None, sender_prefix_list: list = None):
        await cls.add_job("Server", "client_keepalive",
                          {"client_name": client_name,
                           "target_prefix_list": target_prefix_list or [],
                           "sender_prefix_list": sender_prefix_list or []}, wait=False)


@JobQueueClient.action("check_session_native_permission")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    bot: "Bot" = exports["Bot"]
    ctx_manager = bot.ContextSlots[session_info.ctx_slot]
    return {"value": await ctx_manager.check_native_permission(session_info)}


@JobQueueClient.action("send_message")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    bot: "Bot" = exports["Bot"]
    ctx_manager = bot.ContextSlots[session_info.ctx_slot]
    send = await ctx_manager.send_message(session_info, converter.structure(args["message"], MessageChain), quote=args["quote"])
    return {"message_id": send}


@JobQueueClient.action("delete_message")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    bot: "Bot" = exports["Bot"]
    ctx_manager = bot.ContextSlots[session_info.ctx_slot]
    await ctx_manager.delete_message(session_info, message_id=args["message_id"])
    return {"success": True}


@JobQueueClient.action("start_typing")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    bot: "Bot" = exports["Bot"]
    ctx_manager = bot.ContextSlots[session_info.ctx_slot]
    await ctx_manager.start_typing(session_info)
    return {"success": True}


@JobQueueClient.action("end_typing")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    bot: "Bot" = exports["Bot"]
    ctx_manager = bot.ContextSlots[session_info.ctx_slot]
    await ctx_manager.end_typing(session_info)
    return {"success": True}


add_export(JobQueueClient)
