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
from core.server.init import init_async, load_prompt
from core.server.terminate import cleanup_sessions

from core.i18n import build_locale_snapshot, connect_locale_snapshot

stop_event = asyncio.Event()


def inner_ctrl_c_signal_handler(sig, frame):
    """
    处理 Ctrl+C 信号。
    """
    stop_event.set()


signal.signal(signal.SIGINT, inner_ctrl_c_signal_handler)


async def main(process_stop_event=None):
    """服务器主函数。

    执行流程：
    1. 初始化服务器
    2. 启动队列处理任务
    3. 发送重启提示
    4. 持续监听停止事件
    5. 收到停止信号后执行清理
    """
    Logger.info("Starting AkariBot Server...")
    queue_task = None
    try:
        locale_loaded_err = build_locale_snapshot(list(lang_list.keys()), all_locales_path, "akari-bot")
        connect_locale_snapshot("akari-bot")
        await init_async(send_prompt=False)
        queue_task = asyncio.create_task(JobQueueServer.check_job_queue(), name="server-queue-poller")
        # 重启提示须等发起者所在客户端重新上报保活，而保活信号经队列轮询取回，
        # 故置于轮询启动之后；先于轮询发送只会被当作客户端掉线而丢弃。
        await load_prompt(locale_loaded_err)
        while not stop_event.is_set() and not (process_stop_event and process_stop_event.is_set()):
            # 队列轮询是 Server 的生命线。它若因数据库或代码异常退出而主循环仍继续，
            # 进程会表现为在线却不再收发任何消息，守护进程也无法察觉并重启。
            done, _ = await asyncio.wait({queue_task}, timeout=1)
            if queue_task in done:
                if queue_task.cancelled():
                    raise RuntimeError("Server queue poller was cancelled unexpectedly.")
                if error := queue_task.exception():
                    raise error
                raise RuntimeError("Server queue poller stopped unexpectedly.")
    finally:
        Logger.info("Stopping AkariBot Server...")
        await cleanup_sessions()
        # cleanup_sessions 会在释放依赖 Queue 的后台 context 后停止 poller；初始化在
        # poller 建立前失败等路径仍在这里兜底取消局部任务。
        if queue_task is not None:
            if not queue_task.done():
                queue_task.cancel()
            await asyncio.gather(queue_task, return_exceptions=True)
        Logger.success("AkariBot Server stopped successfully.")


def run_async(subprocess: bool = False, binary_mode: bool = False, process_stop_event=None):
    """运行服务器。

    :param subprocess: 是否以子进程模式运行
    :param binary_mode: 是否启用二进制模式
    """
    Info.subprocess = subprocess
    Info.binary_mode = binary_mode
    asyncio.run(main(process_stop_event))


if __name__ == "__main__":
    run_async()
