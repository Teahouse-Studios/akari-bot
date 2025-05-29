import asyncio
from typing import Union

from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.message.chain import MessageChain
from ..builtins.session import SessionInfo
from ..database.models import JobQueuesTable
from core.builtins.parser.message import parser
from ..exports import exports, add_export
from ..utils.alive import Alive


class JobQueueServer(JobQueueBase):

    @classmethod
    async def send_message_signal_to_client(cls, session_info: SessionInfo, message: MessageChain, quote: bool = True):
        value = await cls.add_job(session_info.client_name, "send_message", {"session_info": converter.unstructure(session_info),
                                                                             "message": converter.unstructure(message),
                                                                             'quote': quote})
        return value

    @classmethod
    async def delete_message_signal_to_client(cls, session_info: SessionInfo, message_id: Union[str, list]):
        if isinstance(message_id, str):
            message_id = [message_id]
        value = await cls.add_job(session_info.client_name, "delete_message", {"session_info": converter.unstructure(session_info),
                                                                               "message_id": message_id}, wait=False)
        return value

    @classmethod
    async def start_typing_signal_to_client(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "start_typing", {"session_info": converter.unstructure(session_info)}, wait=False)
        return value

    @classmethod
    async def end_typing_signal_to_client(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "end_typing", {"session_info": converter.unstructure(session_info)}, wait=False)
        return value

    @classmethod
    async def check_session_native_permission(cls, session_info: SessionInfo):
        v = await cls.add_job(session_info.client_name, "check_session_native_permission", {"session_info": converter.unstructure(session_info)})
        return v['value']


@JobQueueServer.action("receive_message_from_client")
async def receive_message_from_client(tsk: JobQueuesTable, args: dict):
    await parser(await exports["Bot"].MessageSession.from_session_info(converter.structure(args['session_info'], SessionInfo)))
    return {"success": True}


@JobQueueServer.action("client_keepalive")
async def client_keepalive(tsk: JobQueuesTable, args: dict):
    Alive.refresh_alive(tsk.args["client_name"],
                        target_prefix_list=tsk.args.get("target_prefix_list"),
                        sender_prefix_list=tsk.args.get("sender_prefix_list"))
    return {"success": True}

add_export(JobQueueServer)
