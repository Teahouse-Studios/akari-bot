from typing import Union

from core.builtins.parser.message import parser
from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.message.chain import MessageChain, MessageNodes
from ..builtins.session.info import SessionInfo
from ..database.models import JobQueuesTable
from ..exports import exports, add_export
from ..utils.alive import Alive


class JobQueueServer(JobQueueBase):

    @classmethod
    async def client_send_message(cls, session_info: SessionInfo, message: MessageChain | MessageNodes, quote: bool = True, wait=True,
                                  enable_parse_message: bool = True,
                                  enable_split_image: bool = True):
        value = await cls.add_job(session_info.client_name, "send_message", {"session_info": converter.unstructure(session_info),
                                                                             "message": converter.unstructure(message, Union[MessageChain, MessageNodes]),
                                                                             'quote': quote,
                                                                             'enable_parse_message': enable_parse_message,
                                                                             'enable_split_image': enable_split_image
                                                                             }, wait=wait)
        return value

    @classmethod
    async def client_delete_message(cls, session_info: SessionInfo, message_id: Union[str, list]):
        if isinstance(message_id, str):
            message_id = [message_id]
        value = await cls.add_job(session_info.client_name, "delete_message", {"session_info": converter.unstructure(session_info),
                                                                               "message_id": message_id}, wait=False)
        return value

    @classmethod
    async def client_start_typing_signal(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "start_typing", {"session_info": converter.unstructure(session_info)})
        return value

    @classmethod
    async def client_end_typing_signal(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "end_typing", {"session_info": converter.unstructure(session_info)})
        return value

    @classmethod
    async def client_error_signal(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "error_signal", {"session_info": converter.unstructure(session_info)}, wait=False)
        return value

    @classmethod
    async def client_check_native_permission(cls, session_info: SessionInfo):
        v = await cls.add_job(session_info.client_name, "check_session_native_permission", {"session_info": converter.unstructure(session_info)})
        return v['value']

    @classmethod
    async def client_hold_context(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "hold_context", {"session_info": converter.unstructure(session_info)})
        return value

    @classmethod
    async def client_release_context(cls, session_info: SessionInfo):
        value = await cls.add_job(session_info.client_name, "release_context", {"session_info": converter.unstructure(session_info)})
        return value


@JobQueueServer.action("receive_message_from_client")
async def receive_message_from_client(tsk: JobQueuesTable, args: dict):
    await parser(await exports["Bot"].MessageSession.from_session_info(
        converter.structure(args['session_info'], SessionInfo)))
    return {"success": True}


@JobQueueServer.action("client_keepalive")
async def client_keepalive(tsk: JobQueuesTable, args: dict):
    Alive.refresh_alive(tsk.args["client_name"],
                        target_prefix_list=tsk.args.get("target_prefix_list"),
                        sender_prefix_list=tsk.args.get("sender_prefix_list"))
    return {"success": True}

add_export(JobQueueServer)
