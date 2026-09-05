"""
服务器初始化模块。

该模块负责服务器启动时的初始化工作，包括：
- 数据库初始化
- 模块加载和注册
- 调度器启动
- 密钥和提示信息加载
"""

import asyncio
import logging

import orjson
from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, I18NContext
from core.builtins.session.info import SessionInfo
from core.config import CFGManager
from core.constants import Info, PrivateAssets, Secret
from core.database import init_db
from core.loader import load_modules, ModulesManager
from core.logger import Logger
from core.scheduler import IntervalTrigger, SchedulerLifecycle
from core.utils.bash import run_sys_command
from .background_tasks import hourly_background_task, start_background_task

# 等待发起重启的客户端重新上报保活的秒数上限。server 与各 bot 子进程一同重启，
# 提示投递时客户端往往尚未就绪；但重启提示并非关键路径，客户端确已掉线时不应无限等待。
RESTART_PROMPT_TIMEOUT = 60


async def init_async(start_scheduler=True, send_prompt=True) -> None:
    """初始化服务器。

    执行服务器启动的所有初始化步骤：
    1. 设置客户端信息和日志
    2. 初始化数据库
    3. 加载所有模块
    4. 初始化定时任务
    5. 初始化后台任务
    6. 加载密钥和启动提示

    Args:
        start_scheduler: 是否启动定时任务（默认True）
        send_prompt: 是否发送重启提示（默认True）。提示须等目标客户端重新上报保活方能投递，
                     而保活信号经队列轮询取回，故由调用方在轮询启动后自行调用 `load_prompt`
    """
    # 设置客户端信息为 "Server"
    Info.client_name = "Server"
    Logger.rename(Info.client_name)

    # 读取版本信息
    version_path = PrivateAssets.path / ".version"
    if version_path.exists():
        with open(version_path, "r") as f:
            Info.version = f.read()
    else:
        returncode, commit_hash, _ = await run_sys_command(["git", "rev-parse", "HEAD"])
        if returncode == 0:
            Info.version = f"git:{commit_hash}"
        else:
            Logger.warning("Failed to get Git commit hash, is it a Git repository?")
    # 初始化数据库
    Logger.info("Initializing database...")
    if not await init_db(generate_schemas=False):
        # pre-init 已统一完成建表；Server 初始化只负责注册连接和全部模块模型。
        raise RuntimeError("Failed to initialize server database.")
    Logger.success("Database initialized successfully.")

    # 加载所有模块
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
    # 初始化后台任务（如 IP 查询、WebRender 等）
    start_background_task()

    # 启动调度器
    if start_scheduler:
        SchedulerLifecycle.start()
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

    # 加载密钥和启动提示
    await load_secret()
    Logger.info(f"Hello, {Info.client_name}!")


async def load_secret():
    """从配置文件中加载所有密钥信息。

    扫描配置中所有带有 "secret" 后缀的配置项，
    将非占位符的值添加到密钥管理系统中，用于内容过滤。
    """
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


async def _wait_for_client_online(client_name: str, timeout: float) -> bool:
    """等待客户端重新上报保活。

    :param client_name: 目标客户端名称
    :param timeout: 等待的秒数上限
    :return: 客户端是否已上线
    """

    async def _poll():
        while not Alive.is_alive(client_name):
            await asyncio.sleep(0.5)

    try:
        await asyncio.wait_for(_poll(), timeout=timeout)
    except asyncio.TimeoutError:
        return False
    return True


async def load_prompt(locale_load_error, timeout: float | None = None) -> None:
    """加载并发送启动提示信息。

    如果存在缓存的发送重启命令的对象信息，发送加载成功或失败的提示。
    清理缓存文件。

    保活表随 server 进程内存一并清空，重启后须等目标客户端重新上报保活方能投递提示，
    否则平台 RPC 会因客户端尚未上线而失败。

    :param locale_load_error: 语言文件加载过程中产生的错误信息
    :param timeout: 等待目标客户端上线的秒数上限，默认为 `RESTART_PROMPT_TIMEOUT`
    """
    author_cache = PrivateAssets.path / ".cache_restart_author"
    loader_cache = PrivateAssets.path / ".cache_loader"
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

        try:
            if not await _wait_for_client_online(
                author_session.client_name, timeout if timeout is not None else RESTART_PROMPT_TIMEOUT
            ):
                Logger.warning(
                    f"Client {author_session.client_name} did not come online in time, skipped restart prompt."
                )
                return

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
