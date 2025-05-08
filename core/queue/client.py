from cattrs import unstructure

from .base import JobQueueBase
from ..builtins.converter import converter
from ..builtins.session import SessionInfo
from ..database.models import JobQueuesTable
from ..exports import exports, add_export


class JobQueueClient(JobQueueBase):

    @classmethod
    async def send_message_to_server(cls, session_info: SessionInfo):
        await cls.add_job("Server", "receive_message_from_client",
                          {"session_info": converter.unstructure(session_info)})


@JobQueueClient.action("validate_permission")
async def _(tsk: JobQueuesTable, args: dict):
    fetch = await exports["Bot"].FetchTarget.fetch_target(args["target_id"], args["sender_id"])
    if fetch:
        await JobQueueClient.return_val(tsk, {"value": await fetch.parent.check_permission()})
    else:
        await JobQueueClient.return_val(tsk, {"value": False})


add_export(JobQueueClient)
