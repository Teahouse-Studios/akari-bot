"""
会话任务管理模块 - 管理等待用户回复和执行回调的任务。

该模块提供了 SessionTaskManager 类，用于管理异步任务队列，
包括等待用户回复和消息回调等功能。
"""

import asyncio
import time
import uuid
from typing import Coroutine, TYPE_CHECKING

from core.constants.exceptions import SessionFinished
from core.exports import add_export
from core.logger import Logger

if TYPE_CHECKING:
    from core.builtins.session.internal import MessageSession


class SessionTaskManager:
    """
    会话任务管理器 - 管理消息会话中的等待任务和回调。

    负责追踪正在进行的异步任务，如等待用户回复，以及执行已发送消息的回调函数。

    数据结构说明:
    ```
        _task_list: {
            origin_target_id: {
                origin_sender_id | "all": {
                    message_session: {
                        'flag': asyncio.Event,  # 用于同步的事件标志
                        'active': bool,          # 任务是否活跃
                        'type': str,             # 任务类型 ('wait' 或 'reply')
                        'reply': tuple[str, ...], # 预期的回复消息 ID（仅 reply 类型）
                        'ts': float,             # 任务创建时间戳
                        'timeout': float,        # 任务超时时间（秒）
                        'result': MessageSession # 任务完成后的结果（可选）
                    }
                }
            }
        }

        _callback_list: {
            message_id: {
                'callback': Coroutine,  # 要执行的回调函数
                'ts': float             # 回调添加时间戳
            }
        }
    ```
    """

    # 存储活跃任务的字典，索引只使用登记时不可变的物理场景／账号 ID。
    # Union ID 和 channel_id 会在等待期间因合并、解绑或重新分配通道而变化；若把
    # 快照作为永久索引，原物理用户会失去自己的 waiter，旧组成员反而可能接管它。
    # check() 会按 incoming 的当前数据库拓扑展开同现实场景和同用户组的物理 ID，
    # 再从这些稳定 bucket 中选择候选。
    _task_list = {}
    _task_sequence = 0

    # 存储待执行回调的字典。key 使用独立注册 token，而不是消息 ID 别名：
    # 两次并发发送可能暂时拥有相同按钮 reply_id，若用别名作 key，后一次会
    # 覆盖前一次，并在发送回包时把 callback 串到错误的物理消息 ID 上。
    # Telegram 等平台的 message_id 只在单个会话内唯一；channel_key 又会把同一现实
    # 场景的多个平台入口合并，二者都不能作为物理消息 ID 的唯一作用域。
    _callback_list = {}
    CALLBACK_TTL = 1800

    @staticmethod
    def _callback_scope(msg: "MessageSession") -> tuple[str | None, str]:
        return msg.session_info.client_name, msg.session_info.target_id

    @classmethod
    def add_task(
        cls,
        msg: "MessageSession",
        flag: asyncio.Event,
        all_: bool = False,
        reply: list[int] | list[str] | int | str | None = None,
        reply_pending: bool = False,
        timeout: float | None = 120,
    ):
        """
        添加一个等待任务到管理器。

        该方法添加一个新的异步任务到队列中，等待用户的回复。

        :param msg: 消息会话对象
        :param flag: 用于同步的 asyncio.Event 对象，任务完成时将被触发
        :param all_: 如果为 True，任务对所有用户生效；否则只对当前用户生效
        :param reply: 期望的回复消息 ID（可以是整数、字符串或列表）
                     如果为 None，表示等待任何回复；否则只等待特定 ID 的回复
        :param timeout: 任务超时时间（秒），默认 120 秒
        """
        # 使用物理 ID 建立稳定索引；Union／channel 都允许在等待期间变化。
        target = msg.session_info.target_id
        sender = msg.session_info.sender_id
        # 根据是否指定了回复 ID 来确定任务类型
        task_type = "reply" if reply or reply_pending else "wait"
        if all_:
            sender = "all"

        # 创建必要的嵌套字典结构
        if target not in cls._task_list:
            cls._task_list[target] = {}
        if sender not in cls._task_list[target]:
            cls._task_list[target][sender] = {}

        # 使用字符串元组保存回复 ID；平台 ID 自身可能包含逗号，不能依赖分隔符拼接。
        if isinstance(reply, list):
            reply = tuple(str(mid) for mid in reply)
        elif reply is not None:
            reply = (str(reply),)

        # 存储任务信息
        cls._task_sequence += 1
        cls._task_list[target][sender][msg] = {
            "flag": flag,  # 同步事件标志
            "active": True,  # 任务初始为活跃状态
            "type": task_type,  # 任务类型
            "reply": reply,  # 期望的回复 ID
            "reply_ready": asyncio.Event(),  # 平台发送完成后才能确定的物理消息 ID
            "ts": time.time(),  # 当前时间戳
            "timeout": timeout,  # 超时设置
            "order": cls._task_sequence,  # 跨用户专属／all 索引的稳定登记顺序
            # reply 的物理 message_id 只在发送它的客户端／平台场景中有意义；
            # 即使两个入口属于同一现实通道，也不能跨平台用碰巧相同的 ID 命中。
            "reply_scope": cls._callback_scope(msg) if task_type == "reply" else None,
        }
        if not reply_pending:
            cls._task_list[target][sender][msg]["reply_ready"].set()
        Logger.debug(cls._task_list)

    @classmethod
    def set_task_reply(
        cls,
        msg: "MessageSession",
        reply: list[int] | list[str] | int | str,
        *,
        all_: bool = False,
    ) -> bool:
        """为发送前预登记的 reply 等待任务补全物理消息 ID。"""
        target_tasks = cls._task_list.get(msg.session_info.target_id, {})
        sender_tasks = target_tasks.get("all" if all_ else msg.session_info.sender_id, {})
        task_info = sender_tasks.get(msg)
        if not task_info or not task_info["active"]:
            return False
        if isinstance(reply, list):
            task_info["reply"] = tuple(str(mid) for mid in reply)
        else:
            task_info["reply"] = (str(reply),)
        task_info["reply_ready"].set()
        return True

    @classmethod
    def add_callback(
        cls,
        msg: "MessageSession",
        message_id: list[int] | list[str] | int | str,
        callback: Coroutine | None,
        fallback_ids: list[int] | list[str] | int | str | None = None,
        *,
        timeout: float | None = CALLBACK_TTL,
        once: bool = False,
    ) -> tuple[tuple[str | None, str], str]:
        """
        为已发送的消息添加一个回调函数。

        当接收到指定消息 ID 的回复时，会自动执行该回调函数。

        :param message_id: 消息 ID（可以是整数、字符串或列表）
        :param callback: 回调协程函数，当回复到达时执行
        :param fallback_ids: 无法取得精确消息 ID 时使用的后备 ID
        :param timeout: callback 有效秒数；默认为 30 分钟，None 表示不自动过期
        :param once: 是否在首次命中后立即失效
        """
        if timeout is not None and timeout <= 0:
            raise ValueError("Callback timeout must be positive or None.")
        # 将同一次发送的全部消息 ID／虚拟按钮 ID／fallback ID 合并为一组；tuple
        # 不会像逗号拼接字符串那样在平台 ID 自身含逗号时产生歧义。
        if isinstance(message_id, list):
            primary_ids = tuple(str(mid) for mid in message_id)
        else:
            primary_ids = (str(message_id),)
        if isinstance(fallback_ids, list):
            fallback = tuple(str(mid) for mid in fallback_ids)
        elif fallback_ids is not None:
            fallback = (str(fallback_ids),)
        else:
            fallback = ()
        # 存储回调信息
        callback_key = (cls._callback_scope(msg), uuid.uuid4().hex)
        cls._callback_list[callback_key] = {
            "callback": callback,  # 要执行的回调
            "ts": time.time(),  # 添加时间戳（用于超时清理）
            "timeout": timeout,
            "once": once,
            # 可重复 callback 必须串行执行，避免同一消息的快速连续操作并发
            # 修改模块状态；一次性 callback 仍会在 await 用户代码前原子删除。
            "lock": asyncio.Lock(),
            "owner_sender_id": msg.session_info.sender_id,
            "primary_ids": tuple(dict.fromkeys(primary_ids)),
            "fallback_ids": frozenset(fallback),
        }
        return callback_key

    @classmethod
    def extend_callback(
        cls,
        callback_key: tuple[tuple[str | None, str], str],
        message_ids: list[int] | list[str] | int | str,
    ) -> tuple[tuple[str | None, str], str] | None:
        """为尚未消费的 callback 补充发送后才取得的物理消息 ID。"""
        callback_info = cls._callback_list.get(callback_key)
        if callback_info is None:
            return None
        if isinstance(message_ids, list):
            additional = tuple(str(mid) for mid in message_ids)
        else:
            additional = (str(message_ids),)
        callback_info["primary_ids"] = tuple(dict.fromkeys(additional + callback_info["primary_ids"]))
        return callback_key

    @classmethod
    def remove_callback(cls, callback_key: tuple[tuple[str | None, str], str] | None) -> None:
        """撤销一组仍在有效期内的 callback 别名。"""
        if callback_key is not None:
            cls._callback_list.pop(callback_key, None)

    @staticmethod
    def _callback_expired(callback_info: dict, now: float | None = None) -> bool:
        """判断 callback 是否已经超过自身有效期。"""
        timeout = callback_info.get("timeout", SessionTaskManager.CALLBACK_TTL)
        return timeout is not None and (time.time() if now is None else now) - callback_info["ts"] >= timeout

    @classmethod
    def get_result(cls, msg: "MessageSession"):
        """
        获取指定任务的执行结果。

        :param msg: 消息会话对象
        :return: 任务完成后的结果（通常是一个 MessageSession 对象），如果没有结果则返回 None
        """
        # 检查是否存在任务结果
        task_info = cls._task_list.get(msg.session_info.target_id, {}).get(msg.session_info.sender_id, {}).get(msg)
        if task_info and "result" in task_info:
            return task_info["result"]
        return None

    @classmethod
    def remove_task(cls, msg: "MessageSession", all_: bool = False) -> dict | None:
        """移除等待任务并清理已经为空的父级索引。"""
        target = msg.session_info.target_id
        sender = "all" if all_ else msg.session_info.sender_id
        target_tasks = cls._task_list.get(target)
        if not target_tasks:
            return None
        sender_tasks = target_tasks.get(sender)
        if not sender_tasks:
            return None

        task_info = sender_tasks.pop(msg, None)
        if task_info:
            task_info["active"] = False
            task_info["reply_ready"].set()
        if not sender_tasks:
            target_tasks.pop(sender, None)
        if not target_tasks:
            cls._task_list.pop(target, None)
        return task_info

    @classmethod
    def get(cls):
        """
        获取整个任务列表。

        :return: 任务列表字典
        """
        return cls._task_list

    @classmethod
    async def bg_check(cls):
        """
        后台检查任务超时。

        该方法应定期调用，用于清理超时的任务和过期的回调。
        超时的任务将被标记为非活跃，其同步标志将被设置。
        """
        # 检查所有活跃任务是否超时
        for target in cls._task_list:
            for sender in cls._task_list[target]:
                for session in cls._task_list[target][sender]:
                    # 检查任务是否活跃
                    if cls._task_list[target][sender][session]["active"]:
                        # 计算任务已经存在的时间
                        elapsed_time = time.time() - cls._task_list[target][sender][session]["ts"]
                        timeout = cls._task_list[target][sender][session].get("timeout", 3600)

                        # 如果超时，标记为不活跃并触发标志
                        if timeout is not None and elapsed_time > timeout:
                            cls._task_list[target][sender][session]["active"] = False
                            # 设置标志，触发等待此标志的协程（无结果 = 取消）
                            cls._task_list[target][sender][session]["reply_ready"].set()
                            cls._task_list[target][sender][session]["flag"].set()

        # 清理超过各自有效期的 callback
        for message_id in cls._callback_list.copy():
            if cls._callback_expired(cls._callback_list[message_id]):
                del cls._callback_list[message_id]

    @classmethod
    async def _active_tasks(cls, session: "MessageSession") -> list[tuple["MessageSession", dict]]:
        """按当前 Union／channel 拓扑返回 incoming 可命中的稳定物理 bucket。"""
        if not cls._task_list:
            return []

        from core.database.models import SenderUnionBind, TargetUnionBind, union_mutation

        target_ids = {session.session_info.target_id}
        sender_ids = {session.session_info.sender_id} if session.session_info.sender_id else set()
        # 绑定与通道变更是低频管理操作。读取候选 bucket 时与它们共用 mutation
        # 域，避免先读旧 Union、再读新 channel 而拼出数据库中从未存在过的范围。
        async with union_mutation():
            target_bind, sender_bind = await asyncio.gather(
                TargetUnionBind.get_or_none(target_id=session.session_info.target_id),
                SenderUnionBind.get_or_none(sender_id=session.session_info.sender_id)
                if session.session_info.sender_id
                else asyncio.sleep(0, result=None),
            )
            queries = []
            if target_bind:
                queries.append(
                    TargetUnionBind.filter(
                        union_id=target_bind.union_id,
                        channel_id=target_bind.channel_id,
                    ).values_list("target_id", flat=True)
                )
            else:
                queries.append(asyncio.sleep(0, result=[]))
            if sender_bind:
                queries.append(
                    SenderUnionBind.filter(union_id=sender_bind.union_id).values_list("sender_id", flat=True)
                )
            else:
                queries.append(asyncio.sleep(0, result=[]))
            current_target_ids, current_sender_ids = await asyncio.gather(*queries)
            target_ids.update(current_target_ids)
            sender_ids.update(current_sender_ids)

        tasks: list[tuple[MessageSession, dict]] = []
        reply_scope = cls._callback_scope(session)
        for target_id in target_ids:
            target_tasks = cls._task_list.get(target_id, {})
            for sender in (*sender_ids, "all"):
                for waiting_session, task_info in list(target_tasks.get(sender, {}).items()):
                    if not task_info["active"]:
                        continue
                    if task_info["type"] == "reply" and task_info["reply_scope"] != reply_scope:
                        continue
                    tasks.append((waiting_session, task_info))
        return sorted(tasks, key=lambda item: item[1]["order"])

    @classmethod
    async def _complete_wait_task(
        cls,
        waiting_session: "MessageSession",
        task_info: dict,
        session: "MessageSession",
    ) -> bool:
        """持有 incoming context 后原子地把消息发布给等待命令。"""
        try:
            await session.hold()
        except Exception:
            Logger.exception("Failed to hold the context of a wait-task result.")
            return False

        # hold_context 会跨进程让出执行权；其间等待命令可能已超时或被取消。
        # 此时不能把结果发布给失效任务，也不能遗留刚取得的 context hold。
        if not task_info["active"]:
            try:
                await session.release()
            except Exception:
                Logger.exception("Failed to release an inactive wait-task result context.")
            return False

        waiting_session._adopt_wait_result(session)
        task_info["result"] = session
        task_info["active"] = False
        task_info["flag"].set()
        return True

    @classmethod
    async def check(cls, session: "MessageSession") -> bool:
        """
        检查新消息是否匹配任何等待中的任务或回调。

        当接收到新消息时调用此方法，检查是否有任务在等待此消息，
        或是否有回调需要执行。

        :param session: 新收到的消息会话
        """
        handled = False

        # pending reply 的物理消息 ID 只有平台发送回包后才知道。先寻找已经 ready
        # 的精确引用目标；若没有，再同时等待所有 pending 任务中的任意一个就绪，
        # 避免较早登记但发送卡住的任务阻塞本可命中的后续 ready 任务。
        while True:
            active_tasks = await cls._active_tasks(session)
            if not active_tasks:
                break

            reply_id = str(session.session_info.reply_id) if session.session_info.reply_id is not None else None
            exact_matches = [
                item
                for item in active_tasks
                if item[1]["type"] == "reply"
                and item[1]["reply_ready"].is_set()
                and reply_id is not None
                and reply_id in (item[1]["reply"] or ())
            ]
            if exact_matches:
                handled = await cls._complete_wait_task(*exact_matches[0], session)
                break

            pending_tasks = [
                task_info
                for _waiting_session, task_info in active_tasks
                if task_info["type"] == "reply" and not task_info["reply_ready"].is_set()
            ]
            if reply_id is not None and pending_tasks:
                readiness_waiters = [
                    asyncio.create_task(task_info["reply_ready"].wait()) for task_info in pending_tasks
                ]
                try:
                    await asyncio.wait(readiness_waiters, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for waiter in readiness_waiters:
                        if not waiter.done():
                            waiter.cancel()
                    await asyncio.gather(*readiness_waiters, return_exceptions=True)
                continue

            wait_matches = [item for item in active_tasks if item[1]["type"] == "wait"]
            if wait_matches:
                handled = await cls._complete_wait_task(*wait_matches[0], session)
            break

        # 等待任务优先消费消息，不能再让同一条回复同时命中 callback 或继续进入 parser。
        if handled:
            return True

        # 没有引用目标时不能命中回调。直接做 str(None) 会得到字面量 "None"，
        # 一旦某个平台或测试注册了同名消息 ID，普通消息也会错误消费该回调。
        if session.session_info.reply_id is None:
            return False

        # 检查当前物理平台场景是否有对此消息的回调需要执行。先选择真实／虚拟
        # 消息 ID 的精确匹配；bot_id fallback 只有在当前作用域和发送者下唯一时
        # 才能使用，否则无法判断用户引用的是哪一次发送，不能按注册顺序猜测。
        exact_matches = []
        fallback_matches = []
        for callback_key, callback_info in list(cls._callback_list.items()):
            # bg_check() 只是周期清理，不能当作授权边界。callback 必须在
            # 尝试命中时按自身 timeout 立即判定是否失效。
            if cls._callback_expired(callback_info):
                cls._callback_list.pop(callback_key, None)
                continue
            callback_scope, _registration_token = callback_key
            if callback_scope != cls._callback_scope(session):
                continue
            if (
                callback_info["owner_sender_id"] is not None
                and callback_info["owner_sender_id"] != session.session_info.sender_id
            ):
                continue
            candidate = (callback_key, callback_info)
            reply_id = str(session.session_info.reply_id)
            if reply_id in callback_info.get("primary_ids", ()):
                exact_matches.append(candidate)
            elif reply_id in callback_info.get("fallback_ids", ()):
                fallback_matches.append(candidate)

        # 真实／虚拟主 ID 比 bot_id fallback 强；但同等级有多个候选时无法
        # 确定用户操作的是哪次发送，必须保留全部注册而不是按字典顺序猜测。
        matched = None
        if len(exact_matches) == 1:
            matched = exact_matches[0]
        elif not exact_matches and len(fallback_matches) == 1:
            matched = fallback_matches[0]
        if matched:
            callback_key, callback_info = matched
            callback = callback_info["callback"]
            if callback_info.get("once", False):
                # 一次性 callback 在 await 用户代码前原子删除，避免并发回复重复执行。
                cls._callback_list.pop(callback_key, None)
                if callback:
                    try:
                        await callback(session)
                    except SessionFinished:
                        # callback 使用 msg.finish() 正常结束当前交互；这是控制流信号，不能
                        # 逸出到 JobQueue action 令任务停在 processing 直到两小时超时。
                        pass
                return True

            async with callback_info["lock"]:
                # 匹配和取得执行锁之间 callback 可能已被发送失败清理、主动撤销
                # 或过期任务删除。执行前重新确认注册身份和有效期，不能让旧引用复活。
                if cls._callback_list.get(callback_key) is not callback_info:
                    return False
                if cls._callback_expired(callback_info):
                    cls._callback_list.pop(callback_key, None)
                    return False
                if callback:
                    try:
                        await callback(session)
                    except SessionFinished:
                        pass
                return True
        return False


# 将 SessionTaskManager 导出到系统的导出列表中
add_export(SessionTaskManager)

# 定义模块公开接口
__all__ = ["SessionTaskManager"]
