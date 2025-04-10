import importlib
import os
import traceback

import orjson as json

from core.constants.path import schedulers_path
from core.database.models import JobQueuesTable
from core.logger import Logger
from core.scheduler import Scheduler, IntervalTrigger
from core.utils.info import Info


def load_extra_schedulers():
    @Scheduler.scheduled_job(IntervalTrigger(hours=12))
    async def clear_queue():
        Logger.info("Clearing job queue...")
        await JobQueuesTable.clear_task()
        Logger.info("Job queue cleared.")

    fun_file = None
    Logger.info("Attempting to load schedulers...")
    if not Info.binary_mode:
        dir_list = os.listdir(schedulers_path)
    else:
        try:
            Logger.warning(
                "Binary mode detected, trying to load pre-built schedulers list..."
            )
            js = "assets/schedulers_list.json"
            with open(js, "r", encoding="utf-8") as f:
                dir_list = json.loads(f.read())
        except Exception:
            Logger.error(
                "Failed to load pre-built schedulers list, using default list."
            )
            dir_list = os.listdir(schedulers_path)

    for file_name in dir_list:
        try:
            file_path = os.path.join(schedulers_path, file_name)
            fun_file = None
            if not Info.binary_mode:
                if os.path.isdir(file_path):
                    if file_name[0] != "_":
                        fun_file = file_name
                elif os.path.isfile(file_path):
                    if file_name[0] != "_" and file_name.endswith(".py"):
                        fun_file = file_name[:-3]
            else:
                if file_name[0] != "_":
                    fun_file = file_name
                if file_name[0] != "_" and file_name.endswith(".py"):
                    fun_file = file_name[:-3]
            if fun_file:
                Logger.debug(f"Loading schedulers.{fun_file}...")
                modules = "schedulers." + fun_file
                importlib.import_module(modules)
                Logger.debug(f"Succeeded loaded schedulers.{fun_file}!")
        except Exception:
            tb = traceback.format_exc()
            errmsg = f"Failed to load schedulers.{fun_file}: \n{tb}"
            Logger.error(errmsg)
    Logger.success("All schedulers loaded.")
