"""
服务器主运行模块。

该模块是服务器的入口点，负责：
- 设置信号处理器（捕获Ctrl+C）
- 启动服务器主循环
- 初始化队列处理
"""

import asyncio
import signal

from core.constants import Info
from core.logger import Logger
from core.queue.server import JobQueueServer
from core.server.init import init_async
from core.server.terminate import cleanup_sessions


stop_event = asyncio.Event()


def inner_ctrl_c_signal_handler(sig, frame):
    """
    处理 Ctrl+C 信号。
    """
    stop_event.set()


signal.signal(signal.SIGINT, inner_ctrl_c_signal_handler)


async def main():
    """服务器主函数。

    执行流程：
    1. 初始化服务器
    2. 启动队列处理任务
    3. 持续监听停止事件
    4. 收到停止信号后执行清理
    """
    Logger.info("Starting AkariBot Server...")
    await init_async()
    asyncio.create_task(JobQueueServer.check_job_queue())
    while not stop_event.is_set():
        await asyncio.sleep(1)
    if stop_event.is_set():
        Logger.info("Stopping AkariBot Server...")
        await cleanup_sessions()
        Logger.success("AkariBot Server stopped successfully.")


def run_async(subprocess: bool = False, binary_mode: bool = False):
    """运行服务器。

    :param subprocess: 是否以子进程模式运行
    :param binary_mode: 是否启用二进制模式
    """
    Info.subprocess = subprocess
    Info.binary_mode = binary_mode
    asyncio.run(main())


if __name__ == "__main__":
    run_async()
