"""
执行锁模块 - 用于管理消息执行锁，防止同一用户的多个命令并发执行。

此模块提供了 ExecutionLockList 类，用于跟踪和控制正在执行的用户命令，
确保同一用户的命令执行顺序和隔离性。
"""

from typing import TYPE_CHECKING

from core.exports import add_export

if TYPE_CHECKING:
    from core.builtins.session.internal import MessageSession


class ExecutionLockList:
    """
    执行锁列表 - 管理正在执行的消息会话。

    通过维护一个锁定用户 ID 的集合，确保同一用户在任何时刻只能有一个命令在执行。
    这防止了由于并发执行导致的竞态条件和数据不一致问题。
    """

    # 存储当前处于锁定状态的用户 ID 集合
    _list = set()

    @staticmethod
    def add(msg: "MessageSession"):
        """
        向执行锁列表中添加用户。

        当用户开始执行命令时调用此方法，将用户 ID 添加到锁定集合中。

        :param msg: 消息会话对象，包含用户信息
        :type msg: MessageSession
        """
        # 从消息会话中获取发送者 ID（用户 ID）
        target_id = msg.session_info.sender_id
        # 将发送者 ID 添加到锁定集合中
        ExecutionLockList._list.add(target_id)

    @staticmethod
    def remove(msg: "MessageSession"):
        """
        从执行锁列表中移除用户。

        当用户命令执行完毕时调用此方法，将用户 ID 从锁定集合中移除。

        :param msg: 消息会话对象，包含用户信息
        :type msg: MessageSession 对象
        """
        # 从消息会话中获取发送者 ID
        target_id = msg.session_info.sender_id
        # 如果该用户在锁定集合中，则移除
        if target_id in ExecutionLockList._list:
            ExecutionLockList._list.remove(target_id)

    @staticmethod
    def check(msg: "MessageSession") -> bool:
        """
        检查用户是否已被锁定。

        用于判断指定用户是否正在执行命令，如果是则应该等待其执行完毕。

        :param msg: 消息会话对象，包含用户信息
        :type msg: MessageSession 对象
        :return: 如果用户已被锁定返回 True，否则返回 False
        :rtype: bool
        """
        # 从消息会话中获取发送者ID
        target_id = msg.session_info.sender_id
        # 检查该用户是否在锁定集合中
        return target_id in ExecutionLockList._list

    @staticmethod
    def get() -> set:
        """
        获取整个执行锁列表。

        返回当前所有被锁定的用户ID集合，用于调试或监控目的。

        :return: 包含所有被锁定用户ID的集合
        :rtype: set
        """
        # 返回当前的锁定集合
        return ExecutionLockList._list


# 将 ExecutionLockList 导出到系统的导出列表中
add_export(ExecutionLockList)

# 定义模块公开接口
__all__ = ["ExecutionLockList"]
