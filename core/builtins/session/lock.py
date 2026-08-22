"""
执行锁模块 - 用于管理消息执行锁，防止同一用户的多个命令并发执行。

此模块提供了 ExecutionLockList 类，用于跟踪和控制正在执行的用户命令，
确保同一用户的命令执行顺序和隔离性。
"""

import asyncio
import uuid
from typing import TYPE_CHECKING

from core.exports import add_export

if TYPE_CHECKING:
    from core.builtins.session.internal import MessageSession


class ExecutionState:
    """仅存在于 Server 进程中的一次命令执行状态。

    同一条命令通过 ``wait_*`` 取得的新 :class:`MessageSession` 会共享此对象，
    因而无论模块后续使用原会话还是回复会话继续等待，操作的都是同一把执行锁。
    ``held_contexts`` 则由原始 parser 执行域在结束时统一释放。
    """

    __slots__ = ("held_contexts", "lock_owner_task", "lock_subject", "lock_token")

    def __init__(self) -> None:
        self.lock_token: str | None = None
        # parser 的根 asyncio.Task 是 lease 的最终生命周期边界。正常路径仍由
        # parser finally 主动释放；若调用链遭遇取消、意外 BaseException 或其它
        # 未覆盖的退出路径，任务完成回调会回收遗留 lease，避免用户永久卡锁。
        self.lock_owner_task: asyncio.Task | None = None
        self.held_contexts: list[MessageSession] = []
        # wait_anyone／wait_reply(all_=True) 取得的结果可能来自另一名用户。
        # continuation 在结果会话上继续 sleep／wait 时，执行锁仍须按最初发起
        # 命令的用户计算，不能把锁主体偷换成回复者。
        self.lock_subject: MessageSession | None = None


class ExecutionLockList:
    """执行锁列表 - 管理正在执行的消息会话。

    每把锁都是一个带随机所有者 token 的 lease，值为获取时该用户的
    Union ID、当前物理账号以及 Union 中的全部绑定账号。检查新会话时
    会重新展开其当前 Union，因此即使等待期间发生 merge／unbind，只要新旧
    身份仍共享任一物理账号，两段执行就不会并发。
    """

    # token -> 该 lease 覆盖的 Union／物理账号键。保留 ``_list`` 名称以兼容
    # 运行时调试和旧测试中的 clear()。
    _list: dict[str, frozenset[str]] = {}
    # 正在扩展身份域的 merge reservation。单独记录 token，才能区分“必须等待
    # 结束的普通命令”和“另一个也在等待扩域的合并命令”，避免后者互相等待。
    _reservations: set[str] = set()
    _changed = asyncio.Event()

    @staticmethod
    def state(msg: "MessageSession") -> ExecutionState:
        """取得会话的 server-only 执行状态，并兼容未调用父类构造器的测试替身。"""
        state = getattr(msg, "_execution_state", None)
        if not isinstance(state, ExecutionState):
            state = ExecutionState()
            msg._execution_state = state
            msg._execution_state_owner = True
        if state.lock_subject is None:
            state.lock_subject = msg
        return state

    @classmethod
    def _subject(cls, msg: "MessageSession") -> "MessageSession":
        """返回该命令执行域稳定的锁主体。"""
        return cls.state(msg).lock_subject or msg

    @staticmethod
    def _local_keys(msg: "MessageSession") -> set[str]:
        """返回无需 I/O 即可确定的身份键。"""
        msg = ExecutionLockList._subject(msg)
        keys = set()
        if msg.session_info.sender_union_id:
            keys.add(msg.session_info.sender_union_id)
        if msg.session_info.sender_id:
            keys.add(msg.session_info.sender_id)
        return keys

    @classmethod
    async def _current_keys(cls, msg: "MessageSession") -> set[str]:
        """展开会话当前 Union 的全部物理账号。"""
        msg = cls._subject(msg)
        sender_id = msg.session_info.sender_id
        keys = {sender_id} if sender_id else set()
        union_info = getattr(msg.session_info, "sender_union_info", None)
        if union_info is not None and sender_id:
            # SessionInfo 是入队时的快照；等待期间 merge／unbind 可能使其
            # sender_union_info 变成已删除的旧行。必须按物理 ID 重新解析，
            # 否则会漏掉新组成员，或在解绑后误锁已分离的账号。
            current_union = await type(union_info).get_by_sender_id(sender_id, create=False)
            if current_union is not None:
                keys.add(current_union.union_id)
                keys.update(await current_union.list_bound_ids())
                return keys
        keys.update(cls._local_keys(msg))
        return keys

    @classmethod
    def _owns_active_lease(cls, msg: "MessageSession") -> bool:
        token = cls.state(msg).lock_token
        return isinstance(token, str) and token in cls._list

    @classmethod
    def _conflicts(cls, keys: set[str]) -> bool:
        return any(keys.intersection(lease_keys) for lease_keys in cls._list.values())

    @classmethod
    def _install(cls, msg: "MessageSession", keys: set[str]) -> None:
        state = cls.state(msg)
        token = uuid.uuid4().hex
        state.lock_token = token
        cls._list[token] = frozenset(keys)
        cls._bind_owner_task(state)

    @classmethod
    def _bind_owner_task(cls, state: ExecutionState) -> None:
        """把执行域绑定到当前根任务，并为非正常退出安装兜底清理。"""
        task = asyncio.current_task()
        if task is None or state.lock_owner_task is task:
            return
        if state.lock_owner_task is not None and not state.lock_owner_task.done():
            # wait_* 的内部辅助 Task 可能共享根执行状态；lease 生命周期仍应由
            # 最初取得它的 parser Task 管理，不能被短命辅助 Task 提前回收。
            return
        state.lock_owner_task = task
        task.add_done_callback(
            lambda finished, execution_state=state: cls._release_finished_owner(execution_state, finished)
        )

    @classmethod
    def _release_finished_owner(cls, state: ExecutionState, finished: asyncio.Task) -> None:
        """在 lease 所属任务结束后同步回收仍遗留的 token。"""
        if state.lock_owner_task is not finished:
            return
        state.lock_owner_task = None
        token = state.lock_token
        state.lock_token = None
        removed = isinstance(token, str) and cls._list.pop(token, None) is not None
        if isinstance(token, str):
            cls._reservations.discard(token)
        if removed:
            cls._notify_changed()

    @classmethod
    def _notify_changed(cls) -> None:
        changed = cls._changed
        cls._changed = asyncio.Event()
        changed.set()

    @classmethod
    async def acquire(cls, msg: "MessageSession", *, wait: bool = False) -> bool:
        """尝试为会话获取 lease。

        :param msg: 要串行化的会话。
        :param wait: 冲突时是否等待现有 lease 释放。
        :return: 成功获取时返回 True；已持有 lease 或非等待模式下存在冲突时
            返回 False。
        """
        if cls._owns_active_lease(msg):
            return False

        # 服务器重载或测试可能清空 lease 表却留下执行域 token。
        # 它已不代表所有权，必须丢弃后重新获取。
        cls.state(msg).lock_token = None

        while True:
            keys = await cls._current_keys(msg)
            if not keys:
                return False
            if not cls._conflicts(keys):
                # _conflicts() 与 _install() 之间没有 await，在同一事件循环中是原子的。
                cls._install(msg, keys)
                return True
            if not wait:
                return False

            changed = cls._changed
            await changed.wait()

    @classmethod
    async def is_locked(cls, msg: "MessageSession") -> bool:
        """按当前 Union 绑定集检查会话是否与现有 lease 冲突。"""
        if cls._owns_active_lease(msg):
            return True
        return cls._conflicts(await cls._current_keys(msg))

    @classmethod
    async def reserve(cls, msg: "MessageSession", keys: set[str]) -> bool:
        """扩展当前 lease 并等待与扩展身份域冲突的其它命令结束。

        Union 合并必须先把双方身份全部加入当前 lease，才能在等待旧命令时
        阻止新的命令进入任一侧。扩展到重叠状态后当前命令只等待，不执行
        合并写入；其它 lease 释放后才取得该身份域的独占权。
        """
        if not cls._owns_active_lease(msg) and not await cls.acquire(msg, wait=True):
            return False
        state = cls.state(msg)
        token = state.lock_token
        if token is None or token not in cls._list:
            return False
        cls._reservations.intersection_update(cls._list)
        reservation = frozenset(set(cls._list[token]).union(keys))
        # 两个合并命令的扩展域只要有交集，后进入 reservation 的命令就必须
        # 主动让出。只检查“完整覆盖”挡不住 A+B 与 B+C 这类部分重叠：双方
        # 扩展后都会等待对方，且再也没有 lease 能释放。
        if any(
            other_token != token
            and other_token in cls._reservations
            and reservation.intersection(cls._list.get(other_token, ()))
            for other_token in tuple(cls._reservations)
        ):
            cls.remove(msg)
            return False
        cls._reservations.add(token)
        cls._list[token] = reservation
        while any(other_token != token and reservation.intersection(other) for other_token, other in cls._list.items()):
            changed = cls._changed
            await changed.wait()
        return True

    @classmethod
    async def refresh(cls, msg: "MessageSession") -> bool:
        """按数据库中的最新 Union 绑定集刷新当前 lease 覆盖范围。"""
        if not cls._owns_active_lease(msg):
            return False
        token = cls.state(msg).lock_token
        keys = await cls._current_keys(msg)
        if token is None or not keys or token not in cls._list:
            return False
        cls._list[token] = frozenset(keys)
        cls._reservations.discard(token)
        cls._notify_changed()
        return True

    @classmethod
    def add(cls, msg: "MessageSession") -> None:
        """兼容无 I/O 的旧调用点，仅使用会话已有的 Union 和物理 ID。

        生产 parser 应使用 :meth:`acquire`，因为只有它会查询最新绑定集。
        """
        if cls._owns_active_lease(msg):
            return
        cls.state(msg).lock_token = None
        keys = cls._local_keys(msg)
        if keys and not cls._conflicts(keys):
            cls._install(msg, keys)

    @classmethod
    def remove(cls, msg: "MessageSession") -> bool:
        """只释放当前会话自己持有的 lease。"""
        state = cls.state(msg)
        token = state.lock_token
        state.lock_token = None
        removed = isinstance(token, str) and cls._list.pop(token, None) is not None
        if isinstance(token, str):
            cls._reservations.discard(token)
        if removed:
            cls._notify_changed()
            return True
        return False

    @classmethod
    def check(cls, msg: "MessageSession") -> bool:
        """无 I/O 的兼容检查；生产 parser 应使用 :meth:`is_locked`。"""
        if cls._owns_active_lease(msg):
            return True
        return cls._conflicts(cls._local_keys(msg))

    @classmethod
    def get(cls) -> set[str]:
        """返回所有活跃 lease 覆盖的身份键，用于调试和管理命令。"""
        return {key for lease_keys in cls._list.values() for key in lease_keys}

    @classmethod
    def count(cls, *, exclude: "MessageSession | None" = None) -> int:
        """返回活跃命令 lease 数，可排除调用命令自身。"""
        excluded_token = cls.state(exclude).lock_token if exclude is not None else None
        return sum(token != excluded_token for token in cls._list)


add_export(ExecutionLockList)

__all__ = ["ExecutionLockList", "ExecutionState"]
