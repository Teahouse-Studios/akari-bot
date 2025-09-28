import asyncio
import logging

import orjson as json
from apscheduler.schedulers import SchedulerAlreadyRunningError

from core.builtins.bot import Bot
from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, I18NContext
from core.builtins.session.info import SessionInfo
from core.config import CFGManager
from core.constants import Info, PrivateAssets, Secret
from core.database import init_db
from core.loader import load_modules, ModulesManager
from core.logger import Logger
from core.scheduler import Scheduler
from core.utils.bash import run_sys_command
from .background_tasks import init_background_task


async def init_async(start_scheduler=True) -> None:
    Info.client_name = "Server"
    Logger.rename(Info.client_name)
    returncode, commit_hash, _ = await run_sys_command(["git", "rev-parse", "HEAD"])
    if returncode == 0:
        Info.version = commit_hash
    else:
        Logger.warning("Failed to get Git commit hash, is it a Git repository?")

    Logger.info("Initializing database...")
    if await init_db():
        Logger.success("Database initialized successfully.")

    await load_modules()
    gather_list = []
    modules = ModulesManager.return_modules_list()
    for x in modules:
        if schedules := modules[x].schedule_list.set:
            for schedule in schedules:
                Scheduler.add_job(
                    func=schedule.function,
                    trigger=schedule.trigger,
                    misfire_grace_time=30,
                    max_instance=1,
                )
    await asyncio.gather(*gather_list)
    asyncio.create_task(init_background_task())
    if start_scheduler:
        try:
            Scheduler.start()
        except SchedulerAlreadyRunningError:
            pass
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    await load_secret()
    Logger.info(f"Hello, {Info.client_name}!")
    await load_prompt()


async def load_secret():
    for x in CFGManager.values:
        for y in CFGManager.values[x].keys():
            if y == "secret" or y.endswith("_secret"):
                for z in CFGManager.values[x][y].keys():
                    w = CFGManager.values[x][y].get(z)
                    if not str(w).startswith("<Replace me"):
                        if isinstance(w, str):
                            Secret.add(w)
                        elif isinstance(w, list):
                            Secret.update(w)


async def load_prompt() -> None:
    author_cache = PrivateAssets.path / ".cache_restart_author"
    loader_cache = PrivateAssets.path / ".cache_loader"
    if author_cache.exists():
        with open(author_cache, "r", encoding="utf-8") as open_author_cache:
            author_session = converter.structure(json.loads(open_author_cache.read()), SessionInfo)
            await author_session.refresh_info()
            with open(loader_cache, "r", encoding="utf-8") as open_loader_cache:
                if (read := open_loader_cache.read()) != "":
                    message = [I18NContext("loader.load.failed"), Plain(read.strip(), disable_joke=True)]
                else:
                    message = I18NContext("loader.load.success")
                message = MessageChain.assign(message)
                await Bot.send_direct_message(author_session, message)
        author_cache.unlink()


__all__ = ["init_async", "load_prompt"]
