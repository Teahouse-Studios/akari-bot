from core.builtins import Bot
from core.logger import Logger
from core.scheduler import CronTrigger
from core.scheduler import Scheduler
from modules.maimai.libraries.maimaidx_api_data import update_alias


@Scheduler.scheduled_job(CronTrigger.from_crontab('0 0 * * *'))
async def maimai_alias():
    Logger.info('Updating maimai alias...')
    await update_alias()