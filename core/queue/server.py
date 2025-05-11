from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.message.chain import MessageChain
from ..builtins.session import SessionInfo
from ..database.models import JobQueuesTable
from ..parser.message import parser
from ..exports import exports, add_export


class JobQueueServer(JobQueueBase):
    @classmethod
    async def send_message_to_client(cls, target_client: str, session_info: SessionInfo, message: MessageChain, quote: bool = True):
        message = MessageChain.assign(message)
        await cls.add_job(target_client, "send_message", {"session_info": converter.unstructure(session_info),
                                                          "message": converter.unstructure(message),
                                                          'quote': quote})


@JobQueueServer.action("receive_message_from_client")
async def receive_message_from_client(tsk: JobQueuesTable, args: dict):
    await parser(await exports["Bot"].MessageSession.from_session_info(converter.structure(args['session_info'], SessionInfo)))
    await JobQueueServer.return_val(tsk, {})

add_export(JobQueueServer)
