import asyncio

from core.builtins.bot import Bot
from core.constants import Info
from core.database import init_db
from core.i18n import connect_locale_snapshot
from core.logger import Logger
from core.queue.client import JobQueueClient


_queue_task: asyncio.Task[None] | None = None
_keepalive_task: asyncio.Task[None] | None = None
_initialization_task: asyncio.Task[None] | None = None


async def check_queue() -> None:
    await JobQueueClient.check_job_queue()


async def _keepalive_loop(
    target_prefix_list: list | None,
    sender_prefix_list: list | None,
) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await JobQueueClient.send_keepalive_signal_to_server(
                Info.client_name,
                target_prefix_list=target_prefix_list,
                sender_prefix_list=sender_prefix_list,
                ctx_slot_index=Bot.fetched_session_ctx_slot,
                features=Bot.ContextSlots[Bot.fetched_session_ctx_slot].features,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception(f"Failed to send keepalive signal for {Info.client_name}: ")


def _restart_finished_task(task: asyncio.Task[None] | None, name: str) -> bool:
    if task is None:
        return True
    if not task.done():
        return False
    if not task.cancelled() and (error := task.exception()) is not None:
        Logger.error(f"{name} stopped unexpectedly: {error!r}")
    return True


async def _client_init_once(
    target_prefix_list: list | None = None,
    sender_prefix_list: list | None = None,
    queue=True,
    load_module_db=False,
    rename_logger: bool = True,
) -> None:
    global _queue_task, _keepalive_task

    if rename_logger:
        Logger.rename(Info.client_name)
    if not await init_db(load_module_db=load_module_db):
        raise RuntimeError(f"Failed to initialize database for {Info.client_name}.")
    await JobQueueClient.send_keepalive_signal_to_server(
        Info.client_name,
        target_prefix_list=target_prefix_list,
        sender_prefix_list=sender_prefix_list,
        ctx_slot_index=Bot.fetched_session_ctx_slot,
        features=Bot.ContextSlots[Bot.fetched_session_ctx_slot].features,
    )
    if queue and _restart_finished_task(_queue_task, "Client queue poller"):
        _queue_task = asyncio.create_task(check_queue(), name=f"{Info.client_name}-queue-poller")
    if _restart_finished_task(_keepalive_task, "Client keepalive task"):
        _keepalive_task = asyncio.create_task(
            _keepalive_loop(target_prefix_list, sender_prefix_list),
            name=f"{Info.client_name}-keepalive",
        )
    connect_locale_snapshot("akari-bot")
    Logger.info(f"Hello, {Info.client_name}!")


async def client_init(
    target_prefix_list: list | None = None,
    sender_prefix_list: list | None = None,
    queue=True,
    load_module_db=False,
    rename_logger: bool = True,
) -> None:
    global _initialization_task

    task = _initialization_task
    if task is not None and task.done() and (task.cancelled() or task.exception() is not None):
        task = None
    if task is None:
        task = asyncio.create_task(
            _client_init_once(
                target_prefix_list,
                sender_prefix_list,
                queue=queue,
                load_module_db=load_module_db,
                rename_logger=rename_logger,
            ),
            name=f"{Info.client_name}-client-init",
        )
        _initialization_task = task
    await asyncio.shield(task)
