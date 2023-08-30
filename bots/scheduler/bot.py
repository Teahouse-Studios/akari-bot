import asyncio
import importlib
import os
import traceback

from core.logger import Logger
from core.utils.i18n import load_locale_file
from core.scheduler import Scheduler

load_dir_path = os.path.abspath('./schedulers/')


def load_modules():
    load_locale_file()
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
            if fun_file is not None:
                Logger.debug(f'Loading schedulers.{fun_file}...')
                modules = 'schedulers.' + fun_file
                importlib.import_module(modules)
                Logger.debug(f'Succeeded loaded schedulers.{fun_file}!')
        except Exception:
            tb = traceback.format_exc()
            errmsg = f'Failed to load schedulers.{fun_file}: \n{tb}'
            Logger.error(errmsg)
    Logger.info('All schedulers loaded.')
    Scheduler.start()


if __name__ == '__main__':
    load_modules()
    Logger.info('Scheduler started.')
    asyncio.get_event_loop().run_forever()
