import asyncio
import os
import shutil
import traceback

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from bot import init_bot
from core.builtins import PrivateAssets, MessageChain, Plain, Bot
from core.builtins.session import SessionInfo
from core.console.info import *
from core.constants.info import Info
from core.constants.path import assets_path, cache_path
from core.server import main
from core.logger import Logger
from core.queue.client import JobQueueClient
from core.terminate import cleanup_sessions
from core.console.context import ConsoleContextManager

Info.dirty_word_check = True
Bot.client_name = client_name
PrivateAssets.set(os.path.join(assets_path, "private", "console"))
console_history_path = os.path.join(PrivateAssets.path, ".console_history")
if os.path.exists(console_history_path):
    os.remove(console_history_path)

if os.path.exists(cache_path):
    shutil.rmtree(cache_path)
os.makedirs(cache_path, exist_ok=True)

ctx_id = Bot.register_context_manager(ConsoleContextManager)


async def console_scheduler():
    ...


async def console_command():
    try:
        session = PromptSession(history=FileHistory(console_history_path))
        asyncio.create_task(main())
        while True:
            m = await asyncio.to_thread(session.prompt)
            await send_command(m)
    except Exception:
        Logger.error(traceback.format_exc())


async def send_command(msg):
    Logger.info("-------Start-------")
    session_data = await SessionInfo.assign(
        target_id=f"{target_prefix}|0",
        sender_id=f"{sender_prefix}|0",
        sender_name="Console",
        target_from=target_prefix,
        sender_from=sender_prefix,
        client_name=client_name,
        message_id='0',
        messages=MessageChain([Plain(msg),]),
        ctx_slot=ctx_id)
    ConsoleContextManager.add_context(session_data, '')
    await JobQueueClient.send_message_to_server(session_data)
    Logger.info("----Process end----")
    # return returns

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
