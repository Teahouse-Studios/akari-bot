from cattr import structure
from cattrs import unstructure

from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.session import SessionInfo
from ..database.models import JobQueuesTable
from ..parser.message import parser
from ..exports import exports, add_export


class JobQueueServer(JobQueueBase):
    @classmethod
    async def send_message_to_client(cls, target_client: str, target_id: str, message):
        await cls.add_job(target_client, "send_message", {"target_id": target_id, "message": message})


@JobQueueServer.action("receive_message_from_client")
async def receive_message_from_client(tsk: JobQueuesTable, args: dict):
    await parser(await exports["Bot"].MessageSession.from_session_info(converter.structure(args['session_info'], SessionInfo)))
    await JobQueueServer.return_val(tsk, {})

add_export(JobQueueServer)
