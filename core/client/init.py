import asyncio

from core.builtins.bot import Bot
from core.builtins.converter import converter
from core.builtins.session.features import Features
from core.constants import Info
from core.database import close_db, init_db
from core.i18n import connect_locale_snapshot
from core.logger import Logger
from core.queue.client import JobQueueClient
from core.queue.rpc import set_default_peer


_queue_task: asyncio.Task[None] | None = None
_initialization_task: asyncio.Task[None] | None = None
QUEUE_RESTART_DELAY = 0.1


async def check_queue() -> None:
    """监督客户端队列轮询；瞬时异常后退避并重新启动。"""
    while True:
        try:
            await JobQueueClient.check_job_queue()
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception(f"Client queue poller for {Info.client_name} stopped unexpectedly, restarting.")
        else:
            Logger.error(f"Client queue poller for {Info.client_name} returned unexpectedly, restarting.")
        await asyncio.sleep(QUEUE_RESTART_DELAY)


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
    global _queue_task

    set_default_peer(JobQueueClient)

    started_tasks: list[tuple[str, asyncio.Task[None]]] = []
    database_attempted = False
    try:
        if rename_logger:
            Logger.rename(Info.client_name)
        database_attempted = True
        if not await init_db(load_module_db=load_module_db, generate_schemas=False):
            raise RuntimeError(f"Failed to initialize database for {Info.client_name}.")
        features = Bot.ContextSlots[Bot.fetched_session_ctx_slot].features
        feature_data = converter.unstructure(features, Features)
        JobQueueClient.configure_peer(
            role="client",
            service=Info.client_name,
            capabilities=["rpc", "signals", *(name for name, supported in feature_data.items() if supported)],
            metadata={
                "target_prefix_list": target_prefix_list or [],
                "sender_prefix_list": sender_prefix_list or [],
                "ctx_slot_index": Bot.fetched_session_ctx_slot,
                "features": feature_data,
            },
        )
        if queue and _restart_finished_task(_queue_task, "Client queue poller"):
            _queue_task = asyncio.create_task(check_queue(), name=f"{Info.client_name}-queue-poller")
            started_tasks.append(("queue", _queue_task))
        if queue:
            await JobQueueClient.wait_ready()
        connect_locale_snapshot("akari-bot")
        Logger.info(f"Hello, {Info.client_name}!")
    except BaseException:
        # 初始化应当具备事务性：后半段失败时撤销本轮刚启动的任务并关闭连接，
        # 使下一次重试从干净状态开始，而不是叠加一组半初始化资源。
        for _, task in started_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*(task for _, task in started_tasks), return_exceptions=True)
        for name, task in started_tasks:
            if name == "queue" and _queue_task is task:
                _queue_task = None
        if database_attempted:
            if started_tasks or JobQueueClient._registered:
                try:
                    await JobQueueClient.begin_shutdown()
                    await JobQueueClient.cancel_process_tasks()
                    await JobQueueClient.stop_job_queue()
                except Exception:
                    Logger.exception(f"Failed to roll back JobQueue peer for {Info.client_name}.")
            await close_db()
        raise


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


async def client_cleanup() -> None:
    """取消客户端初始化和队列任务，并关闭数据库连接。"""
    global _queue_task, _initialization_task
    initialization_task = _initialization_task
    if initialization_task is not None and not initialization_task.done():
        initialization_task.cancel()
        await asyncio.gather(initialization_task, return_exceptions=True)

    queue_task = _queue_task
    if queue_task is not None and not queue_task.done():
        async with JobQueueClient.shutdown_window():
            queue_task.cancel()
            await asyncio.gather(queue_task, return_exceptions=True)
            await JobQueueClient.stop_job_queue()
    else:
        await JobQueueClient.cancel_process_tasks()
        await JobQueueClient.stop_job_queue()
    _initialization_task = None
    _queue_task = None
    await Bot.cancel_pending_messages()
    await close_db()


__all__ = ["check_queue", "client_init", "client_cleanup"]
