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
from apscheduler.schedulers import SchedulerAlreadyRunningError

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
from core.scheduler import Scheduler
from core.utils.bash import run_sys_command
from .background_tasks import init_background_task
from ..i18n import locale_loaded_err

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
    if await init_db():
        Logger.success("Database initialized successfully.")

    # 加载所有模块
    await load_modules()
    gather_list = []
    modules = ModulesManager.return_modules_list()

    # 为各模块配置的定时任务添加到调度器
    for x in modules:
        if not modules[x]._db_load:
            continue

        if schedules := modules[x].schedule_list.set:
            for schedule in schedules:
                Scheduler.add_job(
                    func=schedule.function,
                    trigger=schedule.trigger,
                    misfire_grace_time=30,
                    max_instance=1,
                )
    await asyncio.gather(*gather_list)

    # 初始化后台任务（如 IP 查询、WebRender 等）
    asyncio.create_task(init_background_task())

    # 启动调度器
    if start_scheduler:
        try:
            Scheduler.start()
        except SchedulerAlreadyRunningError:
            pass
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

    # 加载密钥和启动提示
    await load_secret()
    Logger.info(f"Hello, {Info.client_name}!")
    if send_prompt:
        await load_prompt(locale_loaded_err)


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
    否则 `JobQueueServer.add_job` 会以「客户端掉线」为由将其丢弃。

    :param locale_load_error: 语言文件加载过程中产生的错误信息
    :param timeout: 等待目标客户端上线的秒数上限，默认为 `RESTART_PROMPT_TIMEOUT`
    """
    author_cache = PrivateAssets.path / ".cache_restart_author"
    loader_cache = PrivateAssets.path / ".cache_loader"
    if author_cache.exists():
        with open(author_cache, "r", encoding="utf-8") as open_author_cache:
            author_session = converter.structure(orjson.loads(open_author_cache.read()), SessionInfo)
        # 缓存须无条件清理：客户端始终不上线时若将其留下，下次启动会重复投递
        author_cache.unlink()

        if not await _wait_for_client_online(
            author_session.client_name, timeout if timeout else RESTART_PROMPT_TIMEOUT
        ):
            Logger.warning(f"Client {author_session.client_name} did not come online in time, skipped restart prompt.")
            return

        await author_session.refresh_info()
        with open(loader_cache, "r", encoding="utf-8") as open_loader_cache:
            message = []
            if (read := open_loader_cache.read()) != "":
                message += [I18NContext("loader.load.failed"), Plain(read.strip(), disable_joke=True)]
            if locale_load_error:
                message += [Plain("\n".join(locale_load_error), disable_joke=True)]
            if not message:
                message = I18NContext("loader.load.success")
            message = MessageChain.assign(message)
            await Bot.send_direct_message(author_session, message)


__all__ = ["init_async", "load_prompt"]
