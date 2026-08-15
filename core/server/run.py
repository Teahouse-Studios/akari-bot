"""
服务器主运行模块。

该模块是服务器的入口点，负责：
- 设置信号处理器（捕获Ctrl+C）
- 启动服务器主循环
- 初始化队列处理
"""

import asyncio
import signal

from core.constants import Info, lang_list, all_locales_path
from core.logger import Logger
from core.queue.server import JobQueueServer
from core.server.init import init_async, load_prompt, restore_alive_clients
from core.server.terminate import cleanup_sessions

from core.i18n import build_locale_snapshot, connect_locale_snapshot

stop_event: asyncio.Event | None = None


def inner_ctrl_c_signal_handler(sig, frame):
    """
    处理 Ctrl+C 信号。
    """
    del sig, frame
    if stop_event is not None:
        stop_event.set()


async def _wait_for_stop(process_stop_event=None):
    while not (stop_event and stop_event.is_set()) and not (process_stop_event and process_stop_event.is_set()):
        await asyncio.sleep(0.1)


async def _cancel_task(task: asyncio.Task | None, name: str) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()
    result = (await asyncio.gather(task, return_exceptions=True))[0]
    if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
        Logger.error(f"{name} stopped with an error during Server shutdown: {result!r}")


async def _serve(locale_loaded_err):
    queue_task = None
    try:
        await init_async(send_prompt=False)
        restore_alive_clients()
        queue_task = asyncio.create_task(JobQueueServer.check_job_queue(), name="server-job-queue-poller")
        # 重启提示须等发起者所在客户端重新上报保活，而保活信号经队列轮询取回，
        # 故置于轮询启动之后；先于轮询发送只会被当作客户端掉线而丢弃。
        await load_prompt(locale_loaded_err)
        # 正常运行期间轮询器不应退出；若异常结束，向上传播并进入统一清理。
        await queue_task
    finally:
        await _cancel_task(queue_task, "JobQueue poller")


async def main(process_stop_event=None):
    """服务器主函数。

    执行流程：
    1. 初始化服务器
    2. 启动队列处理任务
    3. 发送重启提示
    4. 持续监听停止事件
    5. 收到停止信号后执行清理
    """
    global stop_event
    stop_event = asyncio.Event()
    Logger.info("Starting AkariBot Server...")
    locale_loaded_err = build_locale_snapshot(list(lang_list.keys()), all_locales_path, "akari-bot")
    connect_locale_snapshot("akari-bot")
    serve_task = asyncio.create_task(_serve(locale_loaded_err), name="server-runtime")
    stop_task = asyncio.create_task(_wait_for_stop(process_stop_event), name="server-stop-waiter")
    try:
        done, _ = await asyncio.wait((serve_task, stop_task), return_when=asyncio.FIRST_COMPLETED)
        if serve_task in done:
            await serve_task
    finally:
        await _cancel_task(serve_task, "Server runtime")
        await _cancel_task(stop_task, "Server stop waiter")
        await JobQueueServer.shutdown_workers()
        Logger.info("Stopping AkariBot Server...")
        cleanup_ok = await cleanup_sessions()
        if cleanup_ok:
            Logger.success("AkariBot Server stopped successfully.")
        else:
            Logger.error("AkariBot Server stopped with cleanup errors.")


def run_async(subprocess: bool = False, binary_mode: bool = False, process_stop_event=None):
    """运行服务器。

    :param subprocess: 是否以子进程模式运行
    :param binary_mode: 是否启用二进制模式
    """
    Info.subprocess = subprocess
    Info.binary_mode = binary_mode
    previous_handlers = {}
    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if sig is None:
            continue
        try:
            previous_handler = signal.getsignal(sig)
            signal.signal(sig, inner_ctrl_c_signal_handler)
            previous_handlers[sig] = previous_handler
        except (OSError, ValueError):
            # 非主线程嵌入运行时无法安装进程信号处理器，仍可依赖 process_stop_event。
            pass
    try:
        asyncio.run(main(process_stop_event))
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    run_async()
