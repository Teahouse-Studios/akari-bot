import asyncio

import discord

from bots.discord.info import sender_prefix_list, target_prefix_list
from core.client.init import client_init
from core.config.base import CoreSecretConfig

proxy = CoreSecretConfig.proxy

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
discord_bot = discord.Bot(intents=intents, proxy=proxy)

_client_init_task: asyncio.Task[None] | None = None


async def ensure_client_initialized() -> None:
    """初始化 Discord 客户端，并让并发到达的事件共享同一个初始化任务。"""
    global _client_init_task

    task = _client_init_task
    if task is not None and task.done() and (task.cancelled() or task.exception() is not None):
        task = None

    if task is None:
        task = asyncio.create_task(
            client_init(target_prefix_list, sender_prefix_list),
            name="discord-client-init",
        )
        _client_init_task = task

    await asyncio.shield(task)
