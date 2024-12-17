import asyncio
import os
import shutil
import sys
import traceback

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

import core.scripts.config_generate  # noqa
from core.config import Config
from core.constants.default import db_path_default
from core.constants.info import Info
from core.constants.path import assets_path, cache_path
from core.logger import Logger

if not Config("db_path", default=db_path_default, secret=True):
    raise AttributeError(
        'Wait! You need to fill a valid database address into the config.toml "db_path" field\n'
        'Example: \ndb_path = "sqlite:///database/save.db"\n'
        "(Also you can fill in the above example directly,"
        ' bot will automatically create a SQLite database in the "./database/save.db")'
    )

from bot import init_bot
from core.bot_init import init_async
from core.builtins import PrivateAssets
from core.console.info import *
from core.console.message import MessageSession
from core.extra.scheduler import load_extra_schedulers
from core.parser.message import parser
from core.types import MsgInfo, Session
from core.database import BotDBUtil, session
from core.database.tables import DBVersion

query_dbver = session.query(DBVersion).first()
if not query_dbver:
    session.add_all([DBVersion(value=str(BotDBUtil.database_version))])
    session.commit()
    query_dbver = session.query(DBVersion).first()

if (current_ver := int(query_dbver.value)) < (target_ver := BotDBUtil.database_version):
    print(f"Updating database from {current_ver} to {target_ver}...")
    from core.database.update import update_database

    update_database()
    print("Database updated successfully! Please restart the program.")
    sys.exit()

Info.dirty_word_check = True
PrivateAssets.set(os.path.join(assets_path, "private", "console"))
console_history_path = os.path.join(PrivateAssets.path, ".console_history")
if os.path.exists(console_history_path):
    os.remove(console_history_path)

if os.path.exists(cache_path):
    shutil.rmtree(cache_path)
os.makedirs(cache_path, exist_ok=True)


async def console_scheduler():
    load_extra_schedulers()
    await init_async()


async def console_command():
    try:
        session = PromptSession(history=FileHistory(console_history_path))
        while True:
            m = await asyncio.to_thread(session.prompt, "> ")
            await send_command(m)
    except Exception:
        Logger.error(traceback.format_exc())


async def send_command(msg):
    Logger.info("-------Start-------")
    returns = await parser(
        MessageSession(
            target=MsgInfo(
                target_id=f"{target_prefix}|0",
                sender_id=f"{sender_prefix}|0",
                sender_prefix="Console",
                target_from=target_prefix,
                sender_from=sender_prefix,
                client_name=client_name,
                message_id=0,
            ),
            session=Session(
                message=msg, target=f"{target_prefix}|0", sender=f"{sender_prefix}|0"
            ),
        )
    )
    Logger.info("----Process end----")
    return returns


if __name__ == "__main__":
    init_bot()
    Info.client_name = client_name
    loop = asyncio.new_event_loop()
    loop.run_until_complete(console_scheduler())
    try:
        loop.run_until_complete(console_command())
    except (KeyboardInterrupt, SystemExit):
        print("Exited.")
    finally:
        loop.close()
