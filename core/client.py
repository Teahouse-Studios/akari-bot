import asyncio

from core.bot_init import check_queue
from core.constants import Info
from core.database import init_db
from core.logger import Logger
from core.queue.client import JobQueueClient


async def client_init():
    await init_db()
    asyncio.create_task(check_queue())
    await JobQueueClient.send_keepalive_signal_to_server(Info.client_name)
    Logger.info(f"Hello, {Info.client_name}!")
