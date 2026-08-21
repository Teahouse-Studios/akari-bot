import asyncio

import discord

from bots.discord.info import sender_prefix_list, target_prefix_list
from core.client.init import client_cleanup, client_init
from core.config.base import CoreSecretConfig
from core.logger import Logger

proxy = CoreSecretConfig.proxy

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

_client_init_task: asyncio.Task[None] | None = None


class AkariDiscordBot(discord.Bot):
    async def close(self) -> None:
        global _client_init_task
        try:
            try:
                from bots.discord.context import DiscordContextManager
                from bots.discord.slash_context import DiscordSlashContextManager

                results = await asyncio.gather(
                    DiscordContextManager.shutdown(),
                    DiscordSlashContextManager.shutdown(),
                    return_exceptions=True,
                )
                for result in results:
                    if isinstance(result, BaseException):
                        Logger.error(f"Failed to clean Discord typing state: {result!r}")
            except asyncio.CancelledError:
                raise
            except Exception:
                Logger.exception("Failed to clean Discord adapter state: ")
            await client_cleanup()
        finally:
            _client_init_task = None
            await super().close()


# 所有消息相关操作都使用事件上下文、raw event 或显式 fetch，不需要 Pycord 默认缓存的 1000 条消息。
discord_bot = AkariDiscordBot(intents=intents, proxy=proxy, max_messages=None)


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
