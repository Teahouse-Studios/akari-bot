import asyncio

from core.bot_init import init_async
from core.queue.server import JobQueueServer


async def main():
    await init_async()

    while True:
        await JobQueueServer.check_job_queue("Server")
        await asyncio.sleep(1)
