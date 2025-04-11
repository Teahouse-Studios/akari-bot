import asyncio
import os
import shutil
import traceback

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from bot import init_bot
from core.bot_init import init_async
from core.builtins import PrivateAssets
from core.close import cleanup_sessions
from core.console.info import *
from core.console.message import MessageSession
from core.constants.info import Info
from core.constants.path import assets_path, cache_path
from core.extra.scheduler import load_extra_schedulers
from core.logger import Logger
from core.parser.message import parser
from core.types import MsgInfo, Session

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
            m = await asyncio.to_thread(session.prompt)
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
                sender_name="Console",
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
    import core.scripts.config_generate  # noqa

    loop = asyncio.new_event_loop()
    try:
        init_bot()
        Info.client_name = client_name
        loop.run_until_complete(console_scheduler())
        loop.run_until_complete(console_command())
    except (KeyboardInterrupt, SystemExit):
        print("Exited.")
    finally:
        loop.run_until_complete(cleanup_sessions())
        loop.close()
