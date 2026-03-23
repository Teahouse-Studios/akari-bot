"""
服务器清理和重启模块。

负责服务器的关闭和重启，包括：
- 会话清理
- 任务队列清空
- 调度器关闭
- 数据库连接关闭
"""

import os

from tortoise import Tortoise

# from core.builtins.session.tasks import SessionTaskManager
from core.database.models import JobQueuesTable
from core.logger import Logger
from core.scheduler import Scheduler


async def cleanup_sessions():
    """清理服务器资源。

    执行以下清理步骤：
    1. 清理所有待处理的任务队列
    2. 关闭调度器
    3. 关闭数据库连接
    """
    # get_wait_list = SessionTaskManager.get()
    Logger.warning("Cleaning up sessions...")
    # for x in get_wait_list:
    #     for y in get_wait_list[x]:
    #         for z in get_wait_list[x][y]:
    #             if get_wait_list[x][y][z]["active"]:
    #                 await z.send_message(I18NContext("core.message.restart.prompt"))
    await JobQueuesTable.clear_task(time=0)
    Scheduler.shutdown()
    await Tortoise.close_connections()


async def restart():
    """重启服务器。

    执行清理后强制退出并发出自定义状态码，上级进程会自动重启服务。
    """
    await cleanup_sessions()
    os._exit(233)
