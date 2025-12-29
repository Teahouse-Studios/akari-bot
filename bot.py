import asyncio
import importlib
import multiprocessing
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

from loguru import logger
from tortoise import Tortoise, run_async
from tortoise.exceptions import ConfigurationError

from core.constants import bots_path, config_path, config_filename, logs_path

# Capture the base import lists to avoid clearing essential modules when restarting
base_import_lists = list(sys.modules)

# Basic logger setup

try:
    logger.remove(0)
except ValueError:
    pass

Logger = logger.bind(name="BotDaemon")

logger_format = (
    "<cyan>[BotDaemon]</cyan>"
    "<yellow>[{name}:{function}:{line}]</yellow>"
    "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green>"
    "<level>[{level}]:{message}</level>"
)
Logger.add(
    sys.stdout,
    format=logger_format,
    colorize=True,
    filter=lambda record: record["extra"].get("name") == "BotDaemon"
)
Logger.add(
    sink=logs_path / "BotDaemon_debug_{time:YYYY-MM-DD}.log",
    format=logger_format,
    rotation="00:00",
    retention="1 day",
    level="DEBUG",
    filter=lambda record: record["level"].name == "DEBUG" and record["extra"].get("name") == "BotDaemon",
    encoding="utf8",
)
Logger.add(
    sink=logs_path / "BotDaemon_{time:YYYY-MM-DD}.log",
    format=logger_format,
    rotation="00:00",
    retention="10 days",
    level="INFO",
    encoding="utf8",
    filter=lambda record: record["extra"].get("name") == "BotDaemon"
)

ascii_art = r"""
           _              _   ____        _
     /\   | |            (_) |  _ \      | |
    /  \  | | ____ _ _ __ _  | |_) | ___ | |_
   / /\ \ | |/ / _` | '__| | |  _ < / _ \| __|
  / ____ \|   < (_| | |  | | | |_) | (_) | |_
 /_/    \_\_|\_\__,_|_|  |_| |____/ \___/ \__|
"""
encode = "UTF-8"


class RestartBot(Exception):
    pass


failed_to_start_attempts = {}
disabled_bots = []
processes: list[multiprocessing.Process] = []


def pre_init():

    from core.constants.path import cache_path  # noqa
    if cache_path.exists():
        shutil.rmtree(cache_path)
    cache_path.mkdir(parents=True, exist_ok=True)

    from core.config import Config  # noqa
    from core.constants.default import base_superuser_default  # noqa
    from core.constants.version import database_version  # noqa
    from core.database.link import get_db_link  # noqa
    from core.database.models import SenderInfo, DBVersion  # noqa

    Logger.info(ascii_art)
    if Config("debug", False):
        Logger.debug("Debug mode is enabled.")

    async def update_db():
        await Tortoise.init(
            db_url=get_db_link(),
            modules={"models": ["core.database.models"]}
        )
        await Tortoise.generate_schemas(safe=True)

        query_dbver = await DBVersion.all().first()
        if not query_dbver:
            from core.scripts.convert_database import convert_database

            await Tortoise.close_connections()
            await convert_database()
            Logger.success("Database converted successfully!")
        elif (current_ver := query_dbver.version) < (target_ver := database_version):
            Logger.info(f"Updating database from {current_ver} to {target_ver}...")
            from core.database.update import update_database

            await Tortoise.close_connections()
            await update_database()
            Logger.success("Database updated successfully!")
        else:
            await Tortoise.close_connections()

        base_superuser = Config(
            "base_superuser", base_superuser_default, cfg_type=(str, list)
        )
        if base_superuser:
            if isinstance(base_superuser, str):
                base_superuser = [base_superuser]
            for bu in base_superuser:
                await SenderInfo.update_or_create(defaults={"superuser": True}, sender_id=bu)
        else:
            Logger.warning(
                "The base superuser is not found, please setup it in the config file."
            )

    run_async(update_db())


def clear_import_cache():
    for m in list(sys.modules):
        if m not in base_import_lists:
            del sys.modules[m]


def multiprocess_run_until_complete(func):
    p = multiprocessing.Process(
        target=func,
        daemon=True
    )
    p.start()

    while True:
        if not p.is_alive():
            break
        time.sleep(1)
    terminate_process(p)


def go(bot_name: str, subprocess: bool = False, binary_mode: bool = False):
    from core.constants import Info  # noqa
    from core.logger import Logger  # noqa

    Logger.info(f"[{bot_name}] Here we go!")
    Info.subprocess = subprocess
    Info.binary_mode = binary_mode

    try:
        importlib.import_module(f"bots.{bot_name}.bot")
    except ModuleNotFoundError:
        Logger.exception(f"[{bot_name}] ???, entry not found.")

        sys.exit(1)


async def cleanup_tasks():
    loop = asyncio.get_event_loop()
    asyncio.all_tasks(loop=loop)


binary_mode = not sys.argv[0].endswith(".py")


async def run_bot():
    from core.config import CFGManager  # noqa
    from core.server.run import run_async as server_run_async  # noqa

    def restart_bot_process(bot_name: str):
        if (
                bot_name not in failed_to_start_attempts
                or time.time()
                - failed_to_start_attempts[bot_name]["timestamp"]
                > 60
        ):
            failed_to_start_attempts[bot_name] = {}
            failed_to_start_attempts[bot_name]["count"] = 0
            failed_to_start_attempts[bot_name]["timestamp"] = time.time()
        failed_to_start_attempts[bot_name]["count"] += 1
        failed_to_start_attempts[bot_name]["timestamp"] = time.time()
        if failed_to_start_attempts[bot_name]["count"] >= 3:
            Logger.error(
                f"Bot {bot_name} failed to start 3 times, abort to restart, please check the log."
            )
            return

        Logger.warning(f"Restarting bot {bot_name}...")
        p = multiprocessing.Process(
            target=go,
            args=(bot_name, True, binary_mode,),
            name=bot_name,
            daemon=True
        )
        p.start()
        processes.append(p)

    envs = os.environ.copy()
    envs["PYTHONIOENCODING"] = "UTF-8"
    envs["PYTHONPATH"] = Path(".").resolve()
    bots_list = [p.name for p in bots_path.iterdir() if p.is_dir() and not p.name.startswith("_")]

    for t in CFGManager.values:
        if t.startswith("bot_") and not t.endswith("_secret") and t[4:] in bots_list:
            if "enable" in CFGManager.values[t][t]:
                if not CFGManager.values[t][t]["enable"]:
                    disabled_bots.append(t[4:])
                    Logger.warning(f"Bot {t[4:]} is disabled in config, skip to launch.")
            else:
                Logger.warning(f"Bot {t[4:]} cannot found config \"enable\".")
                disabled_bots.append(t[4:])

    for bl in bots_list:
        if bl in disabled_bots:
            continue
        p = multiprocessing.Process(
            target=go, args=(bl, True, binary_mode), name=bl, daemon=True
        )
        p.start()
        processes.append(p)

    # run the server process
    server_process = multiprocessing.Process(target=server_run_async, args=(True, binary_mode
                                                                            ), name="server", daemon=True)
    server_process.start()
    processes.append(server_process)

    while True:
        for p in processes:
            if p.is_alive():
                continue
            if p.name == "server":
                if p.exitcode == 0:
                    sys.exit(0)
                if p.exitcode == 233:
                    Logger.warning(
                        f"Process {p.pid} (server) exited with code 233, restart all bots."
                    )
                    raise RestartBot
                Logger.critical(f"Process {p.pid} (server) exited with code {p.exitcode}, please check the log.")
                sys.exit(p.exitcode)
            if p.exitcode == 0:
                Logger.warning(
                    f"Process {p.pid} ({p.name}) exited with code 0, abort to restart."
                )
                processes.remove(p)
                terminate_process(p)
                break
            if p.exitcode == 233:
                Logger.warning(
                    f"Process {p.pid} ({p.name}) exited with code 233, restart all bots."
                )
                raise RestartBot
            Logger.critical(
                f"Process {p.pid} ({p.name}) exited with code {p.exitcode}, please check the log."
            )
            processes.remove(p)
            terminate_process(p)
            restart_bot_process(p.name)
            break
        if not processes:
            break
        await asyncio.sleep(1)
    Logger.critical("All bots exited unexpectedly, please check the output.")
    sys.exit(1)


def terminate_process(process: multiprocessing.Process):
    process.kill()
    process.join()
    process.close()


async def main_async():
    if not (config_path / config_filename).exists():
        import core.scripts.config_generate  # noqa

    try:
        multiprocess_run_until_complete(pre_init)
        await run_bot()  # Process will block here so
    except RestartBot as e:
        for ps in processes:
            Logger.warning(f"Terminating process {ps.pid} ({ps.name})...")
            terminate_process(ps)
        processes.clear()
        raise e
    except (KeyboardInterrupt, SystemExit) as e:
        for ps in processes:
            terminate_process(ps)
        processes.clear()
        raise e
    except Exception as e:
        Logger.critical("An error occurred, please check the output.")
        traceback.print_exc()
        raise e
    finally:
        try:
            await Tortoise.close_connections()
        except ConfigurationError:
            pass


def main():
    while True:
        try:
            asyncio.run(main_async())
        except RestartBot:
            clear_import_cache()
            continue
        except (KeyboardInterrupt, SystemExit):
            break


if __name__ == "__main__":
    # Check Python version
    required_version = (3, 12)
    if sys.version_info < required_version:
        Logger.critical(
            f"Your Python version is {sys.version_info.major}.{sys.version_info.minor}, "
            f"and you need Python {required_version[0]}.{required_version[1]} or higher."
        )
        sys.exit(1)

    # Detect if the program is already running
    lock_file_path = Path("./.bot.lock").resolve()
    if sys.platform == "win32":
        import msvcrt

        lock_file = open(lock_file_path, "w")
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            Logger.critical("Another instance is already running. Aborting.")
            sys.exit(1)
    else:
        import fcntl

        lock_file = open(lock_file_path, "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            Logger.critical("Another instance is already running. Aborting.")
            sys.exit(1)

    main()
