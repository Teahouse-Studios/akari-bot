import asyncio

from core.bot_init import init_async
from core.constants import Info
from core.logger import Logger
from core.queue.server import JobQueueServer


async def main():
    Logger.info("Akari Bot Server is starting...")
    await init_async()

    while True:
        await JobQueueServer.check_job_queue("Server")
        await asyncio.sleep(0.1)


def run_async():
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Logger.info("Server stopped by user.")
