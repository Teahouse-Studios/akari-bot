from typing import Union

from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.message.chain import MessageChain
from ..builtins.session import SessionInfo
from ..database.models import JobQueuesTable
from core.builtins.parser.message import parser
from ..exports import exports, add_export


class JobQueueServer(JobQueueBase):

    @classmethod
    async def send_message_to_client(cls, target_client: str, session_info: SessionInfo, message: MessageChain, quote: bool = True):
        message = MessageChain.assign(message)
        value = await cls.add_job(target_client, "send_message", {"session_info": converter.unstructure(session_info),
                                                                  "message": converter.unstructure(message),
                                                                  'quote': quote})
        return value

    @classmethod
    async def delete_message_to_client(cls, target_client: str, session_info: SessionInfo, message_id: Union[str, list]):
        if isinstance(message_id, str):
            message_id = [message_id]
        value = await cls.add_job(target_client, "delete_message", {"session_info": converter.unstructure(session_info),
                                                                    "message_id": message_id}, wait=False)
        return value

    @classmethod
    async def start_typing_to_client(cls, target_client: str, session_info: SessionInfo):
        value = await cls.add_job(target_client, "start_typing", {"session_info": converter.unstructure(session_info)}, wait=False)
        return value

    @classmethod
    async def end_typing_to_client(cls, target_client: str, session_info: SessionInfo):
        value = await cls.add_job(target_client, "end_typing", {"session_info": converter.unstructure(session_info)}, wait=False)
        return value


@JobQueueServer.action("receive_message_from_client")
async def receive_message_from_client(tsk: JobQueuesTable, args: dict):
    await parser(await exports["Bot"].MessageSession.from_session_info(converter.structure(args['session_info'], SessionInfo)))
    await JobQueueServer.return_val(tsk, {})


@JobQueueServer.action("client_keepalive")
async def client_keepalive(tsk: JobQueuesTable, args: dict):
    await JobQueueServer.return_val(tsk, {})

add_export(JobQueueServer)
