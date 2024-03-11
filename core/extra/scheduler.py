import importlib
import os
import traceback

from core.logger import Logger
from core.scheduler import Scheduler, IntervalTrigger
from database import BotDBUtil

load_dir_path = os.path.abspath('./schedulers/')


def load_extra_schedulers():
    @Scheduler.scheduled_job(IntervalTrigger(hours=12))
    async def clear_queue():
        Logger.info('Clearing job queue...')
        BotDBUtil.JobQueue.clear()
        Logger.info('Job queue cleared.')

    fun_file = None
    dir_list = os.listdir(load_dir_path)
    Logger.info('Attempting to load schedulers...')

    for file_name in dir_list:
        try:
            file_path = os.path.join(load_dir_path, file_name)
            fun_file = None
            if os.path.isdir(file_path):
                if file_name[0] != '_':
                    fun_file = file_name
            elif os.path.isfile(file_path):
                if file_name[0] != '_' and file_name.endswith('.py'):
                    fun_file = file_name[:-3]
            if fun_file:
                Logger.debug(f'Loading schedulers.{fun_file}...')
                modules = 'schedulers.' + fun_file
                importlib.import_module(modules)
                Logger.debug(f'Succeeded loaded schedulers.{fun_file}!')
        except Exception:
            tb = traceback.format_exc()
            errmsg = f'Failed to load schedulers.{fun_file}: \n{tb}'
            Logger.error(errmsg)
    Logger.info('All schedulers loaded.')
