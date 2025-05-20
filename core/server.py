import asyncio

from core.bot_init import init_async
from core.logger import Logger
from core.queue.server import JobQueueServer


async def main():
    Logger.info("Akari Bot Server is starting...")
    await init_async()

    while True:
        await JobQueueServer.check_job_queue("Server")
        await asyncio.sleep(1)
