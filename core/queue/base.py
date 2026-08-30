"""
核心队列管理模块，实现异步任务队列的基础功能。

该模块提供了一个分布式任务队列系统，支持在不同的客户端和服务器之间进行
异步任务的调度和执行。主要功能包括：
- 任务的异步添加和追踪
- 任务结果的保存和获取
- 任务执行状态的管理
- 超时处理和错误报告
"""

import asyncio
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext, Plain
from core.builtins.session.info import SessionInfo
from core.config.base import CoreConfig
from core.constants import QueueAlreadyRunning
from core.database.models import JobQueuesTable
from core.exports import exports
from core.logger import Logger
from core.report import send_report


@dataclass
class QueueFinished:
    """表示队列任务完成的数据结构。

    Attributes:
        task_id: 任务的唯一标识符
        action: 执行的操作名称
        status: 任务最终状态（如'done'、'failed'、'timeout'等）
    """

    task_id: str
    action: str
    status: str


class QueueTaskManager:
    """管理队列中待处理任务的内存状态。

    该管理器维护任务的事件同步机制，允许异步等待任务完成并获取结果。
    使用 asyncio.Event 实现任务的完成信号通知。

    Attributes:
        tasks: 字典，存储所有待处理的任务，键为task_id，值为任务状态字典
              包含'flag'（asyncio.Event）和'result'（执行结果）
    """

    tasks = {}
    TASK_TIMEOUT_SECONDS = JobQueuesTable.ACTIVE_TIMEOUT_SECONDS

    @classmethod
    async def add(cls, task_id: str):
        """添加任务并等待其完成。

        该方法会阻塞直到任务完成（通过 set_result 方法设置），然后返回结果。
        无论成功或失败，都会清理任务记录。

        :param task_id: 任务的唯一标识符
        :return: 任务执行的结果字典，如果发生错误返回 None
        """
        try:
            cls.tasks[task_id] = {"flag": asyncio.Event()}
            await asyncio.wait_for(cls.tasks[task_id]["flag"].wait(), timeout=cls.TASK_TIMEOUT_SECONDS)
            return cls.tasks[task_id]["result"]
        except TimeoutError:
            Logger.error(f"Queue task {task_id} timed out while waiting for the remote process.")
            return None
        except Exception as e:
            Logger.error(f"Error in QueueTaskManager: {e}")
            return None
        finally:
            if task_id in cls.tasks:
                del cls.tasks[task_id]

    @classmethod
    async def set_result(cls, task_id: str, result: dict):
        """设置任务结果并通知等待方。

        该方法将结果保存到任务记录，并触发 asyncio.Event 以唤醒等待该任务的协程。

        :param task_id: 任务的唯一标识符
        :param result: 任务执行的结果字典
        """
        if task_id in cls.tasks:
            cls.tasks[task_id]["result"] = result
            cls.tasks[task_id]["flag"].set()


class JobQueueBase:
    """队列任务的基类，定义了队列管理的核心接口和逻辑。

    该类实现了一个通用的异步任务队列系统，支持注册自定义操作处理器，
    定期检查待处理任务，执行任务并收集结果。

    Attributes:
        name: 队列的唯一标识名称，默认使用"Internal|UUID"格式
        queue_actions: 字典，注册的操作处理器，键为操作名称，值为异步处理函数
        report_targets: 错误报告的场景列表，当任务失败时发送错误信息到这些场景
        is_running: 布尔值，表示队列检查循环是否正在运行
        TASK_TIMEOUT_SECONDS: 任务超时时间（秒），超过此时间的任务会被标记为超时
        pause_event: asyncio.Event，用于暂停/恢复队列处理
    """

    name = "Internal|" + str(uuid4())
    queue_actions = {}
    report_targets = CoreConfig.report_targets
    is_running = False
    TASK_TIMEOUT_SECONDS = JobQueuesTable.ACTIVE_TIMEOUT_SECONDS
    pause_event = asyncio.Event()
    pause_event.set()
    _process_tasks: set[asyncio.Task[None]] = set()
    _poll_lock = asyncio.Lock()
    _poller_task: asyncio.Task[None] | None = None
    _shutting_down = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Server 与 Client 在测试中可同时存在于同一解释器；各消费者必须拥有自己的
        # 任务集合、暂停状态和轮询锁，不能通过基类属性互相影响。
        cls._process_tasks = set()
        cls.pause_event = asyncio.Event()
        cls.pause_event.set()
        cls._poll_lock = asyncio.Lock()
        cls._poller_task = None
        cls.is_running = False
        cls._shutting_down = False

    @classmethod
    def _process_task_done(cls, task: asyncio.Task[None]) -> None:
        cls._process_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            Logger.exception(f"Unhandled {cls.__name__} action task failure.")

    @classmethod
    async def cancel_process_tasks(cls) -> None:
        """取消并等待已经领取、仍在运行的 action 处理器。"""
        current = asyncio.current_task()
        # restart() 可由 action 自身触发；排除当前任务，避免它取消并等待自己。
        tasks = [task for task in cls._process_tasks if task is not current]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        cls._process_tasks.difference_update(tasks)

    @classmethod
    async def wait_process_tasks(cls) -> None:
        """等待其它在途 action 完成；调用方自身若也是处理器则自动排除。"""
        current = asyncio.current_task()
        tasks = [task for task in cls._process_tasks if task is not current]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @classmethod
    async def stop_job_queue(cls) -> None:
        """取消并等待当前消费者的队列轮询器。"""
        task = cls._poller_task
        if task is None or task is asyncio.current_task():
            return
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    @classmethod
    async def begin_shutdown(cls) -> None:
        """停止领取新 action，但保留轮询器回收远端任务结果。"""
        cls._shutting_down = True
        cls.pause_event.clear()
        # 与已经读取到 ``claim_new=True`` 的轮询轮次建立屏障。离开此锁后，
        # 轮询器仍可唤醒 QueueTaskManager，但不会再领取新的 action。
        async with cls._poll_lock:
            pass

    @classmethod
    @asynccontextmanager
    async def maintenance_window(cls):
        """暂停领取新任务，排空在途 action 后独占队列数据库访问。

        暂停期间轮询器仍会回收已完成任务的结果，使正在等待客户端回包的 action
        能够正常收尾。等所有其它 action 完成后，再持有轮询锁进入维护区，保证
        关闭或替换数据库连接时没有轮询查询与之并发。
        """
        cls.pause_event.clear()
        try:
            # 等待已经以“允许领取”状态进入的那一轮查询结束。释放锁后，后续轮询
            # 只会泵回终态结果，不会再领取新的 action。
            async with cls._poll_lock:
                pass
            await cls.wait_process_tasks()
            async with cls._poll_lock:
                yield
        finally:
            if not cls._shutting_down:
                cls.pause_event.set()

    @classmethod
    @asynccontextmanager
    async def shutdown_window(cls):
        """停止领取新任务、取消在途 action，并独占队列数据库访问。

        与 :meth:`maintenance_window` 不同，关闭流程不能无限等待可能正在执行网络请求
        或等待远端回包的 action；它需要先阻止轮询器继续领取，再取消并等待已有处理器，
        最后持有轮询锁清空队列和关闭数据库。该窗口也适用于由 Queue action 自身触发的
        ``restart()``：当前处理器会被排除，避免取消并等待自己。
        """
        await cls.begin_shutdown()
        try:
            await cls.cancel_process_tasks()
            async with cls._poll_lock:
                yield
        finally:
            cls._shutting_down = False
            cls.pause_event.set()

    @classmethod
    async def add_job(cls, target_client: str, action, args, wait=True) -> str | dict | None:
        """向队列添加新的任务。

        该方法将任务信息保存到数据库，可选择等待任务完成或立即返回。

        :param target_client: 目标客户端名称，用于将任务路由到特定客户端
        :param action: 操作名称，对应queue_actions中的处理器
        :param args: 操作参数，会被传递给处理器
        :param wait: 是否等待任务完成（默认True）。

            - True: 阻塞直到任务完成，返回执行结果；
            - False: 立即返回任务 ID，不等待执行

        :return wait=True: 返回任务的执行结果字典
        :return wait=False: 返回任务 ID 字符串
        :return target_client 为 None: 返回 None
        """
        # Logger.debug(f"Adding job to queue {cls.name}, target client: {target_client}, action: {action}, args: {args}, wait: {wait}")
        if target_client:
            task_id = await JobQueuesTable.add_task(target_client, action, args)
        else:
            Logger.warning(f"Cannot add job {action} due to target_client being None, perhaps a bug?")
            return None
        if wait:
            return await QueueTaskManager.add(task_id)
        return task_id

    @staticmethod
    async def return_val(tsk: JobQueuesTable, value: dict, status: str = "done") -> QueueFinished:
        """保存任务执行结果并更新任务状态。

        该方法将结果写入数据库，并返回 QueueFinished 对象表示任务完成。

        :param tsk: 任务对象
        :param value: 任务执行的结果字典
        :param status: 任务最终状态（默认"done"）

            - "done": 执行成功
            - "failed": 执行失败
            - "timeout": 执行超时

        :return: QueueFinished 对象，包含任务 ID、操作名称和最终状态
        """
        await tsk.set_val(value, status)
        return QueueFinished(str(tsk.task_id), tsk.action, tsk.status)

    @classmethod
    async def _process_task(cls, tsk: JobQueuesTable):
        """处理单个队列任务。

        该方法执行以下步骤：
        1. 检查任务是否超时
        2. 查找并执行相应的操作处理器
        3. 保存执行结果
        4. 处理任何异常并发送错误报告
        5. 保留终态结果，交由定时清理统一删除

        :param tsk: 待处理的任务对象
        """
        try:
            timestamp = tsk.timestamp
            # 检查任务是否超时
            if time.time() - timestamp.timestamp() > cls.TASK_TIMEOUT_SECONDS:
                Logger.warning(f"Task {tsk.task_id} timeout, skip.")
                tsk_val = await cls.return_val(tsk, {}, status="timeout")
            # 检查操作处理器是否存在
            elif tsk.action in cls.queue_actions:
                # 执行操作处理器
                remaining = cls.TASK_TIMEOUT_SECONDS - (time.time() - timestamp.timestamp())
                returns: dict = await asyncio.wait_for(
                    cls.queue_actions[tsk.action](tsk, tsk.args), timeout=max(remaining, 0)
                )
                tsk_val = await cls.return_val(tsk, returns if returns else {})
            else:
                Logger.warning(f"Unknown action {tsk.action}, skip.")
                tsk_val = await cls.return_val(tsk, {}, status="failed")

            if tsk_val:
                Logger.trace(f"Task {tsk.action}({tsk.task_id}) {tsk.status}.")
                return
            # 下面的代码不应该被执行，如果执行说明有代码 bug
            Logger.error(f"Task {tsk.action}({tsk.task_id}) seems not finished properly, bug in code?")
            await tsk.set_status("failed")
        except asyncio.CancelledError:
            # 处理器可能已经执行了外部副作用（发消息、禁言等），因此取消时不能把任务放回
            # pending 让其它进程重试。写入 failed 终态既避免重复执行，也让等待方及时结束。
            try:
                await asyncio.shield(cls.return_val(tsk, {}, status="failed"))
            except Exception:
                Logger.exception(f"Failed to mark cancelled queue task {tsk.task_id} as failed: ")
            raise
        except TimeoutError:
            Logger.warning(f"Task {tsk.task_id} timed out during action {tsk.action}.")
            await cls.return_val(tsk, {}, status="timeout")
            return
        except Exception:
            # 捕获任何异常并生成错误追踪
            f = traceback.format_exc()
            Logger.error(f)
            await cls.return_val(tsk, {"traceback": f}, status="failed")
            try:
                await send_report(
                    MessageChain.assign(
                        [
                            I18NContext("error.message.report", command=tsk.action),
                            Plain(f.strip(), disable_joke=True, allow_parse=False),
                        ]
                    ),
                    subject=f"AkariBot Queue Error: {tsk.action}",
                    body=f"Action: {tsk.action}\n\n{f.strip()}",
                    direct_sender=lambda target, message: cls.client_direct_message(
                        target, message, disable_secret_check=True
                    ),
                    targets=cls.report_targets,
                )
            except Exception:
                Logger.exception()
            return

    @classmethod
    async def _check_queue(cls, target_client: str | None = None, claim_new: bool = True):
        """检查队列中的待处理任务。

        该方法执行以下步骤：
        1. 检查 QueueTaskManager 中是否有待处理任务，如果已完成则设置其结果
        2. 从数据库中获取待处理和正在处理的任务
        3. 为每个待处理任务创建异步处理任务

        :param target_client: 可选的目标客户端过滤，如果为 None 则获取当前客户端的任务
        """
        # Logger.debug(f"Checking job queue for {cls.name}, target client: {target_client if target_client else "all"}")
        # 检查并设置已完成的任务结果。
        # 该轮询每 100 毫秒执行一次，逐个任务查询会让同时等待的任务数直接乘上查询次数，
        # 故一次取回全部待查任务。
        waiting = list(QueueTaskManager.tasks)
        if waiting:
            for tsk in await JobQueuesTable.filter(task_id__in=waiting):
                if tsk.status not in ["pending", "processing"]:
                    await QueueTaskManager.set_result(str(tsk.task_id), tsk.result)

        # 数据库维护期间只回收远端任务结果，不领取新的 action。不能把整个轮询器
        # 停掉：在途 action 可能正在 QueueTaskManager 中等待客户端回包。
        if not claim_new:
            return
        # Logger.debug([cls.name, target_client if target_client else exports["Bot"].Info.client_name])

        # 获取待处理的任务列表
        get_all = await JobQueuesTable.get_all(
            [cls.name, target_client if target_client else exports["Bot"].Info.client_name]
        )

        # 异步处理所有待处理的任务
        for tsk in get_all:
            Logger.trace(f"Received job queue task {tsk.task_id}, action: {tsk.action}")
            Logger.trace(f"Args: {tsk.args}")
            # 查询 pending 与启动处理之间可能有其它进程读取到同一快照；只有原子领取成功的
            # 消费者才能继续，避免发送消息、禁言等非幂等动作被执行两次。
            if not await tsk.claim():
                continue
            task = asyncio.create_task(cls._process_task(tsk))
            cls._process_tasks.add(task)
            task.add_done_callback(cls._process_task_done)

    @classmethod
    async def check_job_queue(cls, target_client: str | None = None):
        """启动队列检查循环。

        该方法以 100 毫秒的间隔持续检查队列中的任务，直到遇到异常或被外部停止。
        使用 pause_event 控制是否领取新任务。暂停时仍轮询终态结果，避免正在等待
        远端回包的 action 与数据库维护流程互相等待。

        :param target_client: 可选的目标客户端过滤
        :raise QueueAlreadyRunning: 如果队列检查循环已经在运行
        """
        if cls.is_running:
            raise QueueAlreadyRunning
        current = asyncio.current_task()
        cls._poller_task = current
        cls.is_running = True
        try:
            while True:
                async with cls._poll_lock:
                    await cls._check_queue(target_client, claim_new=cls.pause_event.is_set())
                # 以100毫秒的间隔循环检查
                await asyncio.sleep(0.1)
        finally:
            cls.is_running = False
            if cls._poller_task is current:
                cls._poller_task = None

    @classmethod
    def action(cls, action_name: str):
        """装饰器：注册操作处理器。

        使用此装饰器可以为特定的操作名称注册处理函数。
        处理器函数应该是异步函数，接收 JobQueuesTable 对象和参数字典。

        示例:
        ```
            @JobQueueBase.action("my_action")
            async def handle_my_action(tsk: JobQueuesTable, args: dict):
                # 处理逻辑
                return {"result": "success"}
        ```

        :param action_name: 操作的名称

        :return: 装饰器函数
        """

        def decorator(func):
            cls.queue_actions[action_name] = func
            return func

        return decorator

    @classmethod
    async def client_direct_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        disable_secret_check=True,
    ):
        """向客户端发送直接消息。

        该方法通过队列系统异步发送消息，不等待消息发送完成。

        :param session_info: 会话信息对象，包含客户端与场景等信息
        :param message: 要发送的消息链对象
        :param disable_secret_check: 是否禁用密钥检查（默认 True）
        """
        await cls.add_job(
            "Server",
            "client_direct_message",
            {
                "session_info": converter.unstructure(session_info),
                "message": converter.unstructure(message, MessageChain | MessageNodes),
                "disable_secret_check": disable_secret_check,
            },
        )
