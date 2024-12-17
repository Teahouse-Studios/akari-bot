import importlib
import multiprocessing
import os
import shutil
import sys
import traceback
from datetime import datetime
from time import sleep

from loguru import logger as loggerFallback


ascii_art = r"""
           _              _   ____        _
     /\   | |            (_) |  _ \      | |
    /  \  | | ____ _ _ __ _  | |_) | ___ | |_
   / /\ \ | |/ / _` | '__| | |  _ < / _ \| __|
  / ____ \|   < (_| | |  | | | |_) | (_) | |_
 /_/    \_\_|\_\__,_|_|  |_| |____/ \___/ \__|
"""
encode = "UTF-8"

bots_and_required_configs = {
    "aiocqhttp": ["qq_host", "qq_account"],
    "discord": ["discord_token"],
    "aiogram": ["telegram_token"],
    "kook": ["kook_token"],
    "matrix": ["matrix_homeserver", "matrix_user", "matrix_device_id", "matrix_token"],
    "api": [],
    "qqbot": ["qq_bot_appid", "qq_bot_secret"],
}


class RestartBot(Exception):
    pass


failed_to_start_attempts = {}
disabled_bots = []
processes = []


def init_bot():
    import core.scripts.config_generate  # noqa
    from core.config import Config, CFGManager  # noqa
    from core.constants.default import base_superuser_default  # noqa
    from core.database import BotDBUtil, session, DBVersion  # noqa
    from core.logger import Logger  # noqa

    query_dbver = session.query(DBVersion).first()
    if not query_dbver:
        session.add_all([DBVersion(value=str(BotDBUtil.database_version))])
        session.commit()
        query_dbver = session.query(DBVersion).first()
    if (current_ver := int(query_dbver.value)) < (
        target_ver := BotDBUtil.database_version
    ):
        Logger.info(f"Updating database from {current_ver} to {target_ver}...")
        from core.database.update import update_database

        update_database()
        Logger.info("Database updated successfully!")
    print(ascii_art)
    base_superuser = Config(
        "base_superuser", base_superuser_default, cfg_type=(str, list)
    )
    if base_superuser:
        if isinstance(base_superuser, str):
            base_superuser = [base_superuser]
        for bu in base_superuser:
            BotDBUtil.SenderInfo(bu).init()
            BotDBUtil.SenderInfo(bu).edit("isSuperUser", True)
    else:
        Logger.warning(
            "The base superuser was not found, please setup it in the config file."
        )

    disabled_bots.clear()
    for t in CFGManager.values:
        if t.startswith("bot_") and not t.endswith("_secret"):
            if "enable" in CFGManager.values[t][t]:
                if not CFGManager.values[t][t]["enable"]:
                    disabled_bots.append(t[4:])


def multiprocess_run_until_complete(func):
    p = multiprocessing.Process(
        target=func,
    )
    p.start()

    while True:
        if not p.is_alive():
            break
        sleep(1)
    p.terminate()
    p.join()
    p.close()


def go(bot_name: str = None, subprocess: bool = False, binary_mode: bool = False):
    from core.logger import Logger  # noqa
    from core.utils.info import Info  # noqa

    Logger.info(f"[{bot_name}] Here we go!")
    Info.subprocess = subprocess
    Info.binary_mode = binary_mode
    Logger.rename(bot_name)

    try:
        importlib.import_module(f"bots.{bot_name}.bot")
    except ModuleNotFoundError:
        Logger.error(f"[{bot_name}] ???, entry not found.")

        sys.exit(1)


def run_bot():
    from core.constants.path import cache_path  # noqa
    from core.config import Config  # noqa
    from core.logger import Logger  # noqa

    def restart_process(bot_name: str):
        if (
            bot_name not in failed_to_start_attempts
            or datetime.now().timestamp()
            - failed_to_start_attempts[bot_name]["timestamp"]
            > 60
        ):
            failed_to_start_attempts[bot_name] = {}
            failed_to_start_attempts[bot_name]["count"] = 0
            failed_to_start_attempts[bot_name]["timestamp"] = datetime.now().timestamp()
        failed_to_start_attempts[bot_name]["count"] += 1
        failed_to_start_attempts[bot_name]["timestamp"] = datetime.now().timestamp()
        if failed_to_start_attempts[bot_name]["count"] >= 3:
            Logger.error(
                f"Bot {bot_name} failed to start 3 times, abort to restart, please check the log."
            )
            return

        Logger.warning(f"Restarting bot {bot_name}...")
        p = multiprocessing.Process(
            target=go,
            args=(bot_name, True, bool(not sys.argv[0].endswith(".py"))),
            name=bot_name,
        )
        p.start()
        processes.append(p)

    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
    os.makedirs(cache_path, exist_ok=True)
    envs = os.environ.copy()
    envs["PYTHONIOENCODING"] = "UTF-8"
    envs["PYTHONPATH"] = os.path.abspath(".")
    lst = bots_and_required_configs.keys()

    for bl in lst:
        if bl in disabled_bots:
            continue
        if bl in bots_and_required_configs:
            abort = False
            for c in bots_and_required_configs[bl]:
                if not Config(c, _global=True):
                    Logger.error(
                        f"Bot {bl} requires config {c} but not found, abort to launch."
                    )
                    abort = True
                    break
            if abort:
                continue
        p = multiprocessing.Process(
            target=go, args=(bl, True, bool(not sys.argv[0].endswith(".py"))), name=bl
        )
        p.start()
        processes.append(p)
    while True:
        for p in processes:
            if p.is_alive():
                continue
            if p.exitcode == 233:
                Logger.warning(
                    f"{p.pid} ({p.name}) exited with code 233, restart all bots."
                )
                raise RestartBot
            Logger.critical(
                f"Process {p.pid} ({p.name}) exited with code {p.exitcode}, please check the log."
            )
            processes.remove(p)
            p.terminate()
            p.join()
            p.close()
            restart_process(p.name)
            break

        if not processes:
            break
        sleep(1)
    Logger.critical("All bots exited unexpectedly, please check the output.")


if __name__ == "__main__":
    try:
        while True:
            try:
                multiprocess_run_until_complete(init_bot)
                run_bot()  # Process will block here so
                break
            except RestartBot:
                for ps in processes:
                    ps.terminate()
                    ps.join()
                    ps.close()
                processes.clear()
                continue
            except Exception:
                loggerFallback.critical("An error occurred, please check the output.")
                traceback.print_exc()
                break
    except (KeyboardInterrupt, SystemExit):
        for ps in processes:
            ps.terminate()
            ps.join()
            ps.close()
        processes.clear()
