"""服务器初始化模块。"""

import asyncio
import logging

import orjson
from core.builtins.bot import Bot
from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, I18NContext
from core.builtins.session.info import SessionInfo
from core.config import CFGManager
from core.constants import assets_path, Info, PrivateData, Secret
from core.database import init_db
from core.loader import load_modules, ModulesManager
from core.logger import Logger
from core.queue.server import JobQueueServer
from core.queue.backend import create_jobqueue_backend
from core.scheduler import IntervalTrigger, SchedulerLifecycle
from core.utils.bash import run_sys_command
from .background_tasks import hourly_background_task, start_background_task

# 等待发起重启的客户端重新注册为 ready 的秒数上限。server 与各 bot 子进程一同重启，
# 提示投递时客户端往往尚未就绪；但重启提示并非关键路径，客户端确已掉线时不应无限等待。
RESTART_PROMPT_TIMEOUT = 60


async def init_async(start_scheduler=True, send_prompt=True) -> None:
    """初始化服务器。

    Args:
        start_scheduler: 是否启动定时任务（默认True）
        send_prompt: 是否发送重启提示（默认True）。提示须等目标客户端重新注册为 ready 方能投递，
                     故由调用方在数据库和队列启动后自行调用 `load_prompt`
    """
    Info.client_name = "Server"
    JobQueueServer.configure_backend(create_jobqueue_backend())
    JobQueueServer.configure_peer(
        role="server",
        service=Info.client_name,
        capabilities=["rpc", "signals", "modules", "scheduler"],
    )
    Logger.rename(Info.client_name)

    version_path = assets_path / ".version"
    if version_path.exists():
        with open(version_path, "r") as f:
            Info.version = f.read()
    else:
        returncode, commit_hash, _ = await run_sys_command(["git", "rev-parse", "HEAD"])
        if returncode == 0:
            Info.version = f"git:{commit_hash}"
        else:
            Logger.warning("Failed to get Git commit hash, is it a Git repository?")
    Logger.info("Initializing database...")
    if not await init_db(generate_schemas=False):
        # pre-init 已统一完成建表；Server 初始化只负责注册连接和全部模块模型。
        raise RuntimeError("Failed to initialize server database.")
    Logger.success("Database initialized successfully.")

    await load_modules()
    modules = ModulesManager.return_modules_list()

    # 模块与核心 Job 都经统一 wrapper 注册，以便热重载、全局启停和 Server
    # 关闭时能够按稳定 ID 替换，并等待运行中的 coroutine 真正退出。
    SchedulerLifecycle.prepare()
    SchedulerLifecycle.reconcile_all_modules(modules)
    SchedulerLifecycle.register_core_job(
        "hourly-background",
        hourly_background_task,
        IntervalTrigger(minutes=60),
    )
    start_background_task()

    if start_scheduler:
        SchedulerLifecycle.start()
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

    await load_secret()
    Logger.info(f"Hello, {Info.client_name}!")


async def load_secret():
    for x in CFGManager.values:
        for y in CFGManager.values[x].keys():
            if y == "secret" or y.endswith("_secret"):
                for z in CFGManager.values[x][y].keys():
                    w = CFGManager.values[x][y].get(z)
                    if not str(w).startswith("<Replace me"):
                        if isinstance(w, str):
                            Secret.add(w)
                        elif isinstance(w, list):
                            Secret.update(w)


async def _wait_for_client_online(
    client_name: str,
    timeout: float,
    previous_peer_id: str | None = None,
) -> str | None:

    from core.queue.peer import PeerSelector

    async def _poll():
        selector = PeerSelector(roles=("client",), services=(client_name,))
        if previous_peer_id:
            selector = selector.excluding(previous_peer_id)
        while True:
            records = await JobQueueServer.registry.resolve(selector)
            if records:
                for record in records:
                    JobQueueServer._update_peer_cache(record.snapshot())
                return records[0].peer_id
            await asyncio.sleep(0.5)

    try:
        return await asyncio.wait_for(_poll(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


async def load_prompt(locale_load_error, timeout: float | None = None) -> None:
    """加载并发送启动提示信息。

    :param locale_load_error: 语言文件加载过程中产生的错误信息
    :param timeout: 等待目标客户端上线的秒数上限，默认为 `RESTART_PROMPT_TIMEOUT`
    """
    author_cache = PrivateData.path / ".cache_restart_author"
    loader_cache = PrivateData.path / ".cache_loader"
    if author_cache.exists():
        try:
            author_data = author_cache.read_bytes()
        except OSError:
            Logger.exception("Failed to read restart prompt author cache, skipped restart prompt.")
            return
        finally:
            # 缓存须无条件清理：内容损坏、客户端不上线或投递失败时若将其留下，
            # 下次启动会再次解析同一文件，严重时形成稳定的重启循环。
            author_cache.unlink(missing_ok=True)

        try:
            author_session = converter.structure(orjson.loads(author_data), SessionInfo)
        except Exception:
            Logger.exception("Failed to decode restart prompt author cache, skipped restart prompt.")
            return

        # 数据库后端中的旧 Client peer 在进程退出后可能仍保留一段有效租约。它虽然
        # 已无法消费任务，却仍会被普通服务路由视为 ready，因此须明确排除缓存中的旧实例，
        # 并把提示固定投递给本轮重启后实际注册的新实例。
        previous_peer_id = author_session.owner_peer_id

        try:
            replacement_peer_id = await _wait_for_client_online(
                author_session.client_name,
                timeout if timeout is not None else RESTART_PROMPT_TIMEOUT,
                previous_peer_id=previous_peer_id,
            )
            if replacement_peer_id is None:
                Logger.warning(
                    f"Client {author_session.client_name} did not come online in time, skipped restart prompt."
                )
                return
            author_session.owner_peer_id = replacement_peer_id

            await author_session.refresh_info()
            message = []
            try:
                read = loader_cache.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                Logger.exception("Failed to read module loader result cache for restart prompt.")
                read = ""
            if read != "":
                message += [I18NContext("loader.load.failed"), Plain(read.strip(), disable_joke=True)]
            if locale_load_error:
                message += [Plain("\n".join(locale_load_error), disable_joke=True)]
            if not message:
                message = I18NContext("loader.load.success")
            message = MessageChain.assign(message)
            await Bot.send_direct_message(author_session, message)
        except asyncio.CancelledError:
            raise
        except Exception:
            # 重启提示是 best-effort 的辅助信息，不能因为刷新旧会话或平台投递失败
            # 阻止 Server 完成启动。
            Logger.exception("Failed to deliver restart prompt.")


__all__ = ["init_async", "load_prompt"]
