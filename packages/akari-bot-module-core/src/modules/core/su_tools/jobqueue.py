from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.database.models import JobQueuesTable

jobqueue = module("jobqueue", required_superuser=True, base=True)


@jobqueue.command("clear {{I18N:core.help.jobqueue.clear}}")
async def _(msg: Bot.MessageSession):
    await JobQueuesTable.clear_task(time=0, include_active=True)
    await msg.finish(I18NContext("message.success"))
