import traceback

from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.message.chain import MessageChain
from ..builtins.session import SessionInfo
from ..database.models import JobQueuesTable
from ..exports import exports, add_export
from ..logger import Logger


class JobQueueClient(JobQueueBase):

    @classmethod
    async def send_message_to_server(cls, session_info: SessionInfo):
        await cls.add_job("Server", "receive_message_from_client",
                          {"session_info": converter.unstructure(session_info)})

    @classmethod
    async def send_keepalive_to_server(cls, client_name: str):
        await cls.add_job("Server", "client_keepalive", {"client_name": client_name}, wait=False)


@JobQueueClient.action("validate_permission")
async def _(tsk: JobQueuesTable, args: dict):
    fetch = await exports["Bot"].fetch_target(args["target_id"], args["sender_id"])
    if fetch:
        await JobQueueClient.return_val(tsk, {"value": await fetch.parent.check_permission()})
    else:
        await JobQueueClient.return_val(tsk, {"value": False})


@JobQueueClient.action("send_message")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    ctx_manager = exports["Bot"].ContextSlots[session_info.ctx_slot]
    send = await ctx_manager.send_message(session_info, converter.structure(args["message"], MessageChain), quote=args["quote"])
    await JobQueueClient.return_val(tsk, {"message_id": send, "success": True})


@JobQueueClient.action("delete_message")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    ctx_manager = exports["Bot"].ContextSlots[session_info.ctx_slot]
    await ctx_manager.delete_message(session_info, message_id=args["message_id"])
    await JobQueueClient.return_val(tsk, {"success": True})


@JobQueueClient.action("start_typing")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    ctx_manager = exports["Bot"].ContextSlots[session_info.ctx_slot]
    await ctx_manager.start_typing(session_info)
    await JobQueueClient.return_val(tsk, {"success": True})


@JobQueueClient.action("end_typing")
async def _(tsk: JobQueuesTable, args: dict):
    session_info: SessionInfo = converter.structure(args["session_info"], SessionInfo)
    ctx_manager = exports["Bot"].ContextSlots[session_info.ctx_slot]
    await ctx_manager.end_typing(session_info)
    await JobQueueClient.return_val(tsk, {"success": True})


add_export(JobQueueClient)
