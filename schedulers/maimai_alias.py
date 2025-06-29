from core.logger import Logger
from core.scheduler import Scheduler, CronTrigger
from modules.maimai.libraries.maimaidx_apidata import update_alias


@Scheduler.scheduled_job(CronTrigger.from_crontab("0 0 * * *"))
async def update_maimai_alias():
    Logger.info("Updating Maimai alias...")
    await update_alias()
