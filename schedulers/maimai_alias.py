from config import Config
from core.builtins import Bot
from core.logger import Logger
from core.scheduler import CronTrigger, Scheduler
from modules.maimai.libraries.maimaidx_api_data import update_alias


@Scheduler.scheduled_job(CronTrigger.from_crontab('0 0 * * *'))
async def maimai_alias():
    Logger.info('Updating maimai alias...')
    try:
        await update_alias()
    except Exception:
        if Config('debug'):
            Logger.error(traceback.format_exc())